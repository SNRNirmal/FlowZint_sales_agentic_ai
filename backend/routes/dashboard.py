from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from db.database import get_db
from models.approval import Approval
from models.deal import Deal
from models.behavioral_twin import BehavioralTwin

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_db)):
    deals = db.query(Deal).all()
    twins = db.query(BehavioralTwin).all()

    return {
        "total_deals": len(deals),
        "stalled_deals": len([d for d in deals if d.status == "stalled"]),
        # None (JSON null) when no deals exist — truthfully signals "no data"
        # rather than returning 0 which would display as a real score on the
        # frontend. The dashboard MomentumGauge is gated on != null.
        "avg_momentum_score": (
            round(sum(d.momentum_score for d in deals) / len(deals), 1) if deals else None
        ),
        "deals": deals,
        "approver_profiles": twins,
    }


@router.get("/analytics")
def dashboard_analytics(db: Session = Depends(get_db)):
    """Aggregated approval pipeline metrics for the Analytics page.

    All values are derived from real DB rows — no estimates, no heuristics.
    Returns None fields honestly when data is absent (e.g., no approvals yet).
    """
    approvals = db.query(Approval).all()
    twins = db.query(BehavioralTwin).all()
    deals = db.query(Deal).all()

    # --- Approval funnel ---
    total = len(approvals)
    by_status: dict[str, int] = {}
    for a in approvals:
        by_status[a.status] = by_status.get(a.status, 0) + 1

    # --- Department delay from behavioral twins (learned historical data) ---
    dept_delay = [
        {
            "department": t.department,
            "avg_days": t.avg_turnaround_days,
            "total_deals_reviewed": t.total_deals_reviewed,
        }
        for t in sorted(twins, key=lambda t: t.avg_turnaround_days, reverse=True)
    ]

    # --- Predicted vs actual delay accuracy ---
    # Only include approvals where both values are present and actual > 0
    paired = [
        a for a in approvals
        if a.predicted_delay_days is not None and a.actual_delay_days is not None
    ]
    predicted_vs_actual = [
        {
            "department": a.department,
            "predicted": round(a.predicted_delay_days, 1),
            "actual": round(a.actual_delay_days, 1),
        }
        for a in paired
    ]

    # --- Average approval cycle time (actual only, from resolved approvals) ---
    resolved = [a for a in approvals if a.actual_delay_days is not None]
    avg_cycle_days = (
        round(sum(a.actual_delay_days for a in resolved) / len(resolved), 1)
        if resolved else None
    )

    # --- Revenue across deal statuses ---
    revenue_by_status = {
        "active": sum(d.value for d in deals if d.status == "active"),
        "stalled": sum(d.value for d in deals if d.status == "stalled"),
        "closed": sum(d.value for d in deals if d.status == "closed"),
    }

    return {
        "approval_funnel": {
            "total": total,
            "pending": by_status.get("pending", 0),
            "sent": by_status.get("sent", 0),
            "approved": by_status.get("approved", 0),
            "rejected": by_status.get("rejected", 0),
            "escalated": by_status.get("escalated", 0),
        },
        "dept_delay": dept_delay,
        "predicted_vs_actual": predicted_vs_actual,
        "avg_cycle_days": avg_cycle_days,
        "revenue_by_status": revenue_by_status,
        "total_deals": len(deals),
        "total_approvals": total,
    }
