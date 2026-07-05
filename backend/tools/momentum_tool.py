"""Momentum Tool — execution bridge to agents/approval_tracking.py.

Wraps the existing, unchanged compute_momentum_score / momentum_band
functions so the Approval Tracker node (Module 7) calls them via the
same tool-calling contract as every other execution step, instead of
importing agents/approval_tracking.py directly.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from langchain_core.tools import tool, InjectedToolArg
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from agents.approval_tracking import compute_momentum_score, momentum_band

logger = logging.getLogger("threshold.tools.momentum")


class ComputeMomentumInput(BaseModel):
    deal_id: str = Field(..., description="The deal to recompute the Momentum Score for.")


class ComputeMomentumResult(BaseModel):
    success: bool
    deal_id: str | None = None
    momentum_score: int | None = None
    band: str | None = None
    error: str | None = None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _compute(db: Session, deal_id: str) -> int:
    return compute_momentum_score(db, deal_id)


@tool(args_schema=ComputeMomentumInput)
async def compute_momentum(
    deal_id: str,
    db: Annotated[Session, InjectedToolArg],
) -> ComputeMomentumResult:
    """Recompute and persist a deal's Deal Momentum Score.

    Called by the Approval Tracker node after every approval status
    change (sent / approved / rejected), so the dashboard always
    reflects current state.
    """
    logger.info("compute_momentum called", extra={"deal_id": deal_id})

    try:
        score = await asyncio.to_thread(_compute, db, deal_id)
        return ComputeMomentumResult(
            success=True, deal_id=deal_id, momentum_score=score, band=momentum_band(score)
        )
    except Exception as exc:
        logger.error(
            "Momentum computation failed after retries",
            extra={"deal_id": deal_id, "error": str(exc)},
            exc_info=True,
        )
        return ComputeMomentumResult(success=False, error=f"Momentum computation failed: {exc}")
