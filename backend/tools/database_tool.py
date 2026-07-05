"""Database Tool — execution bridge for Approval persistence.

nodes/approval_detection.py produces in-memory ApprovalStatus objects
with fresh UUIDs but never writes them to the database — that would
be a side effect inside a "pure reasoning" node, which the node's own
docstring explicitly says it must not have. This tool is where that
persistence actually happens, called by whichever node runs after
approval detection in the compiled graph (Module 9).

Architecture position:
  Reasoning Node (approval_detection)  →  database_tool  →  models/approval.py
       decides WHAT approvals exist        WRITES them        system of record

Design notes mirror crm_tool.py:
  - Async via asyncio.to_thread() over the existing sync SQLAlchemy layer.
  - InjectedToolArg hides the DB session from the LLM tool schema.
  - tenacity retry for transient DB failures.
  - Idempotent create: re-running detection for the same deal_id does
    not duplicate approval rows already persisted with the same
    approval_id.
"""

from __future__ import annotations

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

from models.approval import Approval
from schemas.graph_state import ApprovalStatus

logger = logging.getLogger("threshold.tools.database")


# -----------------------------------------------------------------------
# Pydantic v2 Input / Output Schemas
# -----------------------------------------------------------------------

class PersistApprovalsInput(BaseModel):
    """Input schema for persist_approvals. Accepts the exact
    ApprovalStatus list produced by nodes/approval_detection.py."""

    deal_id: str = Field(..., description="The deal these approvals belong to.")
    approvals: list[ApprovalStatus] = Field(
        ..., description="Approval records to persist, as produced by the Approval Detection node."
    )


class PersistApprovalsResult(BaseModel):
    success: bool
    persisted_count: int = 0
    skipped_existing_count: int = 0
    error: str | None = None


class UpdateApprovalStatusInput(BaseModel):
    """Input schema for update_approval_status."""

    approval_id: str = Field(..., description="The approval record to update.")
    status: str = Field(
        ...,
        description="New status: pending | sent | approved | rejected | escalated.",
    )
    predicted_delay_days: float | None = None
    actual_delay_days: float | None = None
    artifact_format_used: str | None = None


class UpdateApprovalStatusResult(BaseModel):
    success: bool
    approval_id: str | None = None
    previous_status: str | None = None
    new_status: str | None = None
    error: str | None = None


VALID_APPROVAL_STATUSES: set[str] = {"pending", "sent", "approved", "rejected", "escalated"}


# -----------------------------------------------------------------------
# Internal retry-wrapped DB helpers
# -----------------------------------------------------------------------

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _persist_approvals_in_db(
    db: Session, deal_id: str, approvals: list[ApprovalStatus]
) -> tuple[int, int]:
    """Writes approval rows, skipping any approval_id that already
    exists (idempotency guard against re-running detection)."""
    persisted = 0
    skipped = 0

    for approval in approvals:
        existing = db.query(Approval).filter(Approval.id == approval.approval_id).first()
        if existing is not None:
            skipped += 1
            continue

        db.add(
            Approval(
                id=approval.approval_id,
                deal_id=deal_id,
                department=approval.department,
                approver_id=approval.approver_id,
                status=approval.status,
                predicted_delay_days=approval.predicted_delay_days,
                actual_delay_days=approval.actual_delay_days,
                artifact_format_used=approval.artifact_format_used,
            )
        )
        persisted += 1

    db.commit()
    return persisted, skipped


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _update_approval_in_db(
    db: Session,
    approval_id: str,
    status: str,
    predicted_delay_days: float | None,
    actual_delay_days: float | None,
    artifact_format_used: str | None,
) -> Approval | None:
    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    if approval is None:
        return None

    approval.status = status
    if predicted_delay_days is not None:
        approval.predicted_delay_days = predicted_delay_days
    if actual_delay_days is not None:
        approval.actual_delay_days = actual_delay_days
    if artifact_format_used is not None:
        approval.artifact_format_used = artifact_format_used

    db.commit()
    db.refresh(approval)
    return approval


# -----------------------------------------------------------------------
# LangChain Tools (async)
# -----------------------------------------------------------------------

@tool(args_schema=PersistApprovalsInput)
async def persist_approvals(
    deal_id: str,
    approvals: list[ApprovalStatus],
    db: Annotated[Session, InjectedToolArg],
) -> PersistApprovalsResult:
    """Persist Approval Detection's in-memory results to the database.

    Idempotent: approval_ids already present in the database are
    skipped rather than duplicated, so this is safe to call again if
    a node retries after a partial failure.
    """
    logger.info(
        "persist_approvals called",
        extra={"deal_id": deal_id, "count": len(approvals)},
    )

    try:
        import asyncio

        persisted, skipped = await asyncio.to_thread(
            _persist_approvals_in_db, db, deal_id, approvals
        )
        logger.info(
            "Approvals persisted",
            extra={"deal_id": deal_id, "persisted": persisted, "skipped": skipped},
        )
        return PersistApprovalsResult(
            success=True, persisted_count=persisted, skipped_existing_count=skipped
        )

    except Exception as exc:
        logger.error(
            "Persisting approvals failed after retries",
            extra={"deal_id": deal_id, "error": str(exc)},
            exc_info=True,
        )
        return PersistApprovalsResult(success=False, error=f"Persist failed: {exc}")


@tool(args_schema=UpdateApprovalStatusInput)
async def update_approval_status(
    approval_id: str,
    status: str,
    db: Annotated[Session, InjectedToolArg],
    predicted_delay_days: float | None = None,
    actual_delay_days: float | None = None,
    artifact_format_used: str | None = None,
) -> UpdateApprovalStatusResult:
    """Update an approval's status and optional delay/artifact fields.

    Used by the Approval Tracker node (after Human Review approves a
    send) and by the Learning node (when recording an actual delay).
    """
    logger.info(
        "update_approval_status called",
        extra={"approval_id": approval_id, "status": status},
    )

    if status not in VALID_APPROVAL_STATUSES:
        return UpdateApprovalStatusResult(
            success=False,
            error=f"Invalid status '{status}'. Valid: {sorted(VALID_APPROVAL_STATUSES)}",
        )

    try:
        import asyncio

        approval = await asyncio.to_thread(
            _fetch_previous_status, db, approval_id
        )
        previous_status = approval.status if approval else None

        updated = await asyncio.to_thread(
            _update_approval_in_db,
            db,
            approval_id,
            status,
            predicted_delay_days,
            actual_delay_days,
            artifact_format_used,
        )

        if updated is None:
            return UpdateApprovalStatusResult(
                success=False, error=f"Approval '{approval_id}' not found."
            )

        logger.info(
            "Approval status updated",
            extra={
                "approval_id": approval_id,
                "previous_status": previous_status,
                "new_status": status,
            },
        )
        return UpdateApprovalStatusResult(
            success=True,
            approval_id=approval_id,
            previous_status=previous_status,
            new_status=status,
        )

    except Exception as exc:
        logger.error(
            "Approval status update failed after retries",
            extra={"approval_id": approval_id, "error": str(exc)},
            exc_info=True,
        )
        return UpdateApprovalStatusResult(
            success=False, error=f"Update failed: {exc}"
        )


def _fetch_previous_status(db: Session, approval_id: str) -> Approval | None:
    """Small helper to read current status before overwriting it,
    purely for the before/after audit trail in the result object."""
    return db.query(Approval).filter(Approval.id == approval_id).first()
