"""Approval routes — Human Review checkpoint endpoints.

These endpoints are the UI-facing half of the human-in-the-loop design:
  - POST /{id}/send   → human approves the drafted nudge; sends to Slack
  - POST /{id}/hold   → human holds the draft; nothing is sent
  - POST /{id}/resolve → human records the actual outcome; triggers Learning

All three are synchronous FastAPI routes backed by SQLAlchemy. Tool-layer
public functions (compute_momentum_score, record_outcome_sync) are called
directly so the route stays synchronous without blocking the event loop
on LangChain async machinery.

No imports from agents.* — all business logic is now in tools/.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.database import get_db
from integrations.slack_client import send_slack_message
from models.approval import Approval
from models.deal import Deal
from tools.momentum_tool import compute_momentum_score
from tools.learning_tool import record_outcome_sync
from services.deal_service import resume_deal_graph

router = APIRouter(prefix="/approvals", tags=["approvals"])

# Even a glacial enterprise approval resolves within a year; anything larger
# is a data-entry error that would poison the twin's rolling average.
MAX_DELAY_DAYS = 365.0


@router.get("/")
def list_approvals(db: Session = Depends(get_db)):
    """Return all approvals across all deals.

    Eliminates the N+1 fan-out pattern the frontend used to perform
    (GET /deals/ + N × GET /deals/{id}). The frontend filters by status
    client-side using the approval.status field.
    """
    return db.query(Approval).all()


@router.post("/{approval_id}/send")
async def send_approval_nudge(approval_id: str, nudge_text: str, db: Session = Depends(get_db)):
    """Human Review Checkpoint: 'Send' button. Nothing reaches a real
    approver until a human explicitly approves this action."""

    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    send_slack_message(channel=f"#{approval.department.lower()}-approvals", text=nudge_text)
    approval.status = "sent"
    db.commit()

    # Resume graph execution (completes pipeline)
    await resume_deal_graph(deal_id=approval.deal_id, action="approve")

    return {"status": "sent", "approval_id": approval_id}


@router.post("/{approval_id}/hold")
async def hold_approval_nudge(approval_id: str, db: Session = Depends(get_db)):
    """Human Review Checkpoint: 'Hold' button — draft stays pending,
    nothing is sent. Routes back to regenerate."""
    
    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
        
    # Resume graph execution (loops back for changes)
    await resume_deal_graph(deal_id=approval.deal_id, action="request_changes")
    
    return {"status": "held", "approval_id": approval_id}


@router.post("/{approval_id}/resolve")
def resolve_approval(
    approval_id: str,
    actual_delay_days: float = Query(..., ge=0, le=MAX_DELAY_DAYS, allow_inf_nan=False),
    artifact_format_used: str = Query(..., min_length=1, max_length=100),
    delay_reason: str = Query("", max_length=500),
    db: Session = Depends(get_db),
):
    """Marks an approval as approved and triggers the Learning Agent to
    update that approver's Behavioral Twin.

    Bounds mirror RecordOutcomeInput (tools/learning_tool.py): a negative,
    infinite, or NaN delay would flow into update_twin_after_deal and
    corrupt avg_turnaround_days / fastest_responding_format."""

    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    approval.status = "approved"
    approval.actual_delay_days = actual_delay_days
    approval.artifact_format_used = artifact_format_used
    db.commit()

    record_outcome_sync(
        db,
        deal_id=approval.deal_id,
        approver_id=approval.approver_id,
        actual_delay_days=actual_delay_days,
        artifact_format_used=artifact_format_used,
        delay_reason=delay_reason,
    )

    new_score = compute_momentum_score(db, approval.deal_id)
    return {"status": "approved", "new_momentum_score": new_score}
