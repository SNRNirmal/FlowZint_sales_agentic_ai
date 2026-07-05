"""Learning Agent — after a deal/approval closes, updates the
approver's Behavioral Twin using a weighted rolling average, and logs
the outcome for future root-cause analysis."""

import uuid

from sqlalchemy.orm import Session
from models.learning_log import LearningLog
from behavioral_twins.twin_store import update_twin_after_deal


def record_outcome(
    db: Session,
    deal_id: str,
    approver_id: str,
    actual_delay_days: float,
    artifact_format_used: str,
    delay_reason: str = "",
) -> None:
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
