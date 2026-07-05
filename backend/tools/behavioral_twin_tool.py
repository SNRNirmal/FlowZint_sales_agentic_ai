"""Behavioral Twin Tool — execution bridge to memory/behavioral_twin_store.py.

This is the tool-calling wrapper around the Module 2 memory layer.
Reasoning nodes (Delay Intelligence, Module 6) never call
memory/behavioral_twin_store.py directly — they call this tool, which
adds the same async/retry/typed-result conventions as every other
tool in this layer, and keeps the "separate reasoning from execution"
requirement structurally enforced: a node can only reach the twin
store through a tool call, never an import.

Architecture position:
  Reasoning Node  →  behavioral_twin_tool  →  memory/behavioral_twin_store.py
     needs twin        executes read/write        (Module 2, unchanged)
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

from memory.behavioral_twin_store import get_twin_snapshot, persist_twin_update
from schemas.graph_state import BehavioralTwinSnapshot

logger = logging.getLogger("threshold.tools.behavioral_twin")


# -----------------------------------------------------------------------
# Pydantic v2 Input / Output Schemas
# -----------------------------------------------------------------------

class GetTwinInput(BaseModel):
    approver_id: str = Field(..., description="The approver whose behavioral twin to fetch.")
    department: str = Field(
        ..., description="Department, used to construct a default profile if no twin exists yet."
    )


class GetTwinResult(BaseModel):
    success: bool
    twin: BehavioralTwinSnapshot | None = None
    error: str | None = None


class UpdateTwinInput(BaseModel):
    approver_id: str = Field(..., description="The approver whose twin to update.")
    actual_delay_days: float = Field(..., ge=0.0, description="Actual approval turnaround time.")
    artifact_format_used: str = Field(..., description="The artifact format that was used for this approval.")


class UpdateTwinResult(BaseModel):
    success: bool
    twin: BehavioralTwinSnapshot | None = None
    error: str | None = None


# -----------------------------------------------------------------------
# Internal retry-wrapped calls into the memory layer
# -----------------------------------------------------------------------

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _get_twin(db: Session, approver_id: str, department: str) -> BehavioralTwinSnapshot:
    return get_twin_snapshot(db, approver_id, department)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _update_twin(
    db: Session, approver_id: str, actual_delay_days: float, artifact_format_used: str
) -> BehavioralTwinSnapshot:
    return persist_twin_update(db, approver_id, actual_delay_days, artifact_format_used)


# -----------------------------------------------------------------------
# LangChain Tools (async)
# -----------------------------------------------------------------------

@tool(args_schema=GetTwinInput)
async def get_behavioral_twin(
    approver_id: str,
    department: str,
    db: Annotated[Session, InjectedToolArg],
) -> GetTwinResult:
    """Fetch an approver's Behavioral Twin profile.

    Returns a low-confidence default profile (confidence=0.0) rather
    than an error if no twin exists yet — the caller's conditional
    routing (Module 4's edges) decides what to do with low confidence,
    this tool only reports it.
    """
    logger.info("get_behavioral_twin called", extra={"approver_id": approver_id})

    try:
        twin = await asyncio.to_thread(_get_twin, db, approver_id, department)
        return GetTwinResult(success=True, twin=twin)
    except Exception as exc:
        logger.error(
            "get_behavioral_twin failed after retries",
            extra={"approver_id": approver_id, "error": str(exc)},
            exc_info=True,
        )
        return GetTwinResult(success=False, error=f"Twin fetch failed: {exc}")


@tool(args_schema=UpdateTwinInput)
async def update_behavioral_twin(
    approver_id: str,
    actual_delay_days: float,
    artifact_format_used: str,
    db: Annotated[Session, InjectedToolArg],
) -> UpdateTwinResult:
    """Apply the Learning node's weighted-rolling-average update to an
    approver's Behavioral Twin. Delegates entirely to the existing,
    unchanged update_twin_after_deal logic via the memory layer — this
    tool adds no new business logic, only the tool-calling contract.
    """
    logger.info(
        "update_behavioral_twin called",
        extra={"approver_id": approver_id, "actual_delay_days": actual_delay_days},
    )

    try:
        twin = await asyncio.to_thread(
            _update_twin, db, approver_id, actual_delay_days, artifact_format_used
        )
        logger.info(
            "Behavioral twin updated",
            extra={
                "approver_id": approver_id,
                "new_avg_turnaround_days": twin.avg_turnaround_days,
                "total_deals_reviewed": twin.total_deals_reviewed,
            },
        )
        return UpdateTwinResult(success=True, twin=twin)
    except Exception as exc:
        logger.error(
            "update_behavioral_twin failed after retries",
            extra={"approver_id": approver_id, "error": str(exc)},
            exc_info=True,
        )
        return UpdateTwinResult(success=False, error=f"Twin update failed: {exc}")
