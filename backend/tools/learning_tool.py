"""Learning Tool — execution bridge to agents/learning.py.

Wraps the existing record_outcome function (which itself calls
memory/behavioral_twin_store.persist_twin_update and writes the
learning_log row) as a single tool-calling step for the Learning node
(Module 8). Kept as one tool, not split across behavioral_twin_tool.py,
because "close out this approval's learning" is one atomic business
operation — a twin update with no corresponding learning_log entry
would be an inconsistent write.
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

from agents.learning import record_outcome
from memory.behavioral_twin_store import get_twin_snapshot
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
    record_outcome(
        db,
        deal_id=deal_id,
        approver_id=approver_id,
        actual_delay_days=actual_delay_days,
        artifact_format_used=artifact_format_used,
        delay_reason=delay_reason,
    )


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
