"""Approval Tracking Agent — updates approval status and computes the
live Deal Momentum Score."""

from sqlalchemy.orm import Session
from models.deal import Deal
from models.approval import Approval

WEIGHTS = {
    "delay_risk": 15,
    "pending_approval": 8,
    "sla_breach": 20,
    "completed_approval": 10,
    "proactive_action": 5,
}


def compute_momentum_score(db: Session, deal_id: str) -> int:
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
    if score >= 80:
        return "green"
    if score >= 50:
        return "yellow"
    return "red"
