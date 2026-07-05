"""Momentum Tool — computes and persists a deal's Deal Momentum Score.

Self-contained: all business logic lives here. The Approval Tracker
node (Module 7) calls this tool via the standard tool-calling contract;
no code in the graph layer imports models or SQLAlchemy directly.
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

from models.deal import Deal
from models.approval import Approval

logger = logging.getLogger("threshold.tools.momentum")

# ---------------------------------------------------------------------------
# Business logic (previously in agents/approval_tracking.py)
# ---------------------------------------------------------------------------

WEIGHTS = {
    "delay_risk": 15,
    "pending_approval": 8,
    "sla_breach": 20,
    "completed_approval": 10,
    "proactive_action": 5,
}


def compute_momentum_score(db: Session, deal_id: str) -> int:
    """Recompute and persist the Deal Momentum Score for a given deal."""
    approvals = db.query(Approval).filter(Approval.deal_id == deal_id).all()

    score = 100
    for approval in approvals:
        if approval.status == "pending":
            score -= WEIGHTS["pending_approval"]
        if approval.status == "approved":
            score += WEIGHTS["completed_approval"]
        if approval.predicted_delay_days and approval.predicted_delay_days > 5:
            score -= WEIGHTS["delay_risk"]

    score = max(0, min(100, score))

    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if deal:
        deal.momentum_score = score
        deal.status = "stalled" if score < 50 else "active"
        db.commit()

    return score


def momentum_band(score: int) -> str:
    """Return a colour-coded risk band for the given momentum score."""
    if score >= 80:
        return "green"
    if score >= 50:
        return "yellow"
    return "red"


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
