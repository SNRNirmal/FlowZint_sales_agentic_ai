from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from models.approval import Approval
from models.deal import Deal
from integrations.slack_client import send_slack_message
from agents.approval_tracking import compute_momentum_score
from agents.learning import record_outcome

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("/{approval_id}/send")
def send_approval_nudge(approval_id: str, nudge_text: str, db: Session = Depends(get_db)):
    """Human Review Checkpoint: 'Send' button. Nothing reaches a real
    approver until a human explicitly approves this action."""

    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    send_slack_message(channel=f"#{approval.department.lower()}-approvals", text=nudge_text)
    approval.status = "sent"
    db.commit()

    return {"status": "sent", "approval_id": approval_id}


@router.post("/{approval_id}/hold")
def hold_approval_nudge(approval_id: str, db: Session = Depends(get_db)):
    """Human Review Checkpoint: 'Hold' button — draft stays pending,
    nothing is sent."""
    return {"status": "held", "approval_id": approval_id}


@router.post("/{approval_id}/resolve")
def resolve_approval(
    approval_id: str,
    actual_delay_days: float,
    artifact_format_used: str,
    delay_reason: str = "",
    db: Session = Depends(get_db),
):
    """Marks an approval as approved and triggers the Learning Agent to
    update that approver's Behavioral Twin."""

    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    approval.status = "approved"
    approval.actual_delay_days = actual_delay_days
    approval.artifact_format_used = artifact_format_used
    db.commit()

    record_outcome(
        db,
        deal_id=approval.deal_id,
        approver_id=approval.approver_id,
        actual_delay_days=actual_delay_days,
        artifact_format_used=artifact_format_used,
        delay_reason=delay_reason,
    )

    new_score = compute_momentum_score(db, approval.deal_id)
    return {"status": "approved", "new_momentum_score": new_score}
