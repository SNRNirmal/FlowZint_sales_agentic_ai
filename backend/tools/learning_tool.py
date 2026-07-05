"""Learning Tool — records approval outcomes and updates Behavioral Twins.

Self-contained: the record_outcome business logic lives here directly.
Wraps twin-update + learning_log write as one atomic tool-calling step
for the Learning node (Module 8). Kept as one tool, not split, because
a twin update with no learning_log entry would be an inconsistent write.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
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

from behavioral_twins.twin_store import update_twin_after_deal
from memory.behavioral_twin_store import get_twin_snapshot
from models.learning_log import LearningLog
from schemas.graph_state import BehavioralTwinSnapshot

logger = logging.getLogger("threshold.tools.learning")


class RecordOutcomeInput(BaseModel):
    deal_id: str = Field(..., description="The deal this approval belonged to.")
    approver_id: str = Field(..., description="The approver whose outcome is being recorded.")
    actual_delay_days: float = Field(..., ge=0.0)
    artifact_format_used: str = Field(...)
    delay_reason: str = Field(default="")


class RecordOutcomeResult(BaseModel):
    success: bool
    updated_twin: BehavioralTwinSnapshot | None = None
    error: str | None = None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _record(
    db: Session,
    deal_id: str,
    approver_id: str,
    actual_delay_days: float,
    artifact_format_used: str,
    delay_reason: str,
) -> None:
    """Update the approver's Behavioral Twin and write a learning_log row.

    This is the former agents/learning.py record_outcome() logic, inlined
    here so the agents/ package can be deleted without breaking this tool.
    """
    update_twin_after_deal(
        db,
        approver_id=approver_id,
        actual_delay_days=actual_delay_days,
        artifact_format_used=artifact_format_used,
    )

    log = LearningLog(
        id=str(uuid.uuid4()),
        deal_id=deal_id,
        approver_id=approver_id,
        delay_reason=delay_reason,
        successful_action=artifact_format_used,
        approval_duration_days=actual_delay_days,
    )
    db.add(log)
    db.commit()


def record_outcome_sync(
    db: Session,
    deal_id: str,
    approver_id: str,
    actual_delay_days: float,
    artifact_format_used: str,
    delay_reason: str = "",
) -> None:
    """Public synchronous entry point for the learning-outcome write.

    Delegates entirely to ``_record`` (which carries the tenacity retry
    decorator). Exists so callers — primarily synchronous FastAPI routes —
    can import a public symbol instead of crossing a private boundary.
    """
    _record(db, deal_id, approver_id, actual_delay_days, artifact_format_used, delay_reason)


@tool(args_schema=RecordOutcomeInput)
async def record_approval_outcome(
    deal_id: str,
    approver_id: str,
    actual_delay_days: float,
    artifact_format_used: str,
    db: Annotated[Session, InjectedToolArg],
    delay_reason: str = "",
) -> RecordOutcomeResult:
    """Close the learning loop for one approved deal.

    Updates the approver's Behavioral Twin (weighted rolling average)
    and writes a learning_log row in one atomic call, then reads back
    the updated twin so the Learning node's returned GraphState update
    reflects the new profile immediately (no separate re-fetch needed).
    """
    logger.info(
        "record_approval_outcome called",
        extra={"deal_id": deal_id, "approver_id": approver_id},
    )

    try:
        await asyncio.to_thread(
            _record, db, deal_id, approver_id, actual_delay_days, artifact_format_used, delay_reason
        )

        # Read back the just-updated twin. department isn't known here,
        # but get_twin_snapshot only uses it for the zero-twin default
        # path, which cannot apply immediately after a successful update.
        updated_twin = await asyncio.to_thread(
            get_twin_snapshot, db, approver_id, ""
        )

        logger.info(
            "Learning outcome recorded",
            extra={
                "deal_id": deal_id,
                "approver_id": approver_id,
                "new_avg_turnaround_days": updated_twin.avg_turnaround_days,
            },
        )
        return RecordOutcomeResult(success=True, updated_twin=updated_twin)

    except Exception as exc:
        logger.error(
            "record_approval_outcome failed after retries",
            extra={"deal_id": deal_id, "approver_id": approver_id, "error": str(exc)},
            exc_info=True,
        )
        return RecordOutcomeResult(success=False, error=f"Learning record failed: {exc}")
