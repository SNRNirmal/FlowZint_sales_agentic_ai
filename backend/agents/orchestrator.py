"""Orchestrator Agent — owns deal state and coordinates every other
agent in sequence. Entry point called by the CRM webhook route."""

from sqlalchemy.orm import Session

from agents.approval_detection import detect_required_approvals
from agents.delay_intelligence import predict_delay
from agents.document_generation import generate_artifact
from agents.communication import draft_nudge
from agents.approval_tracking import compute_momentum_score
from models.deal import Deal
from models.approval import Approval


def process_new_deal(db: Session, deal: Deal) -> list[dict]:
    """Runs the full pipeline for a newly created deal:
    detect approvals -> predict delay -> draft artifact -> draft nudge.
    Returns a list of drafted actions awaiting human review — nothing
    is sent automatically."""

    deal_dict = {
        "value": deal.value,
        "product_type": deal.product_type,
        "discount_percent": deal.discount_percent,
        "customer_segment": deal.customer_segment,
        "customer_name": deal.customer_name,
    }

    required_approvals = detect_required_approvals(deal_dict)
    drafted_actions = []

    for req in required_approvals:
        prediction = predict_delay(db, deal_dict, req["approver_id"])

        approval = Approval(
            deal_id=deal.id,
            department=req["department"],
            approver_id=req["approver_id"],
            status="pending",
            predicted_delay_days=prediction["expected_delay_days"],
        )
        db.add(approval)
        db.commit()
        db.refresh(approval)

        artifact = generate_artifact(db, deal_dict, req["approver_id"], req["department"])

        urgency = "high" if prediction["delay_probability"] > 0.6 else "normal"
        nudge = draft_nudge(deal_dict, req["department"], urgency, prediction["root_cause"])

        drafted_actions.append({
            "approval_id": approval.id,
            "department": req["department"],
            "approver_id": req["approver_id"],
            "prediction": prediction,
            "artifact_draft": artifact,
            "nudge_draft": nudge,
            "review_status": "awaiting_human_review",  # Send / Edit / Hold happens in the UI
        })

    compute_momentum_score(db, deal.id)
    return drafted_actions
