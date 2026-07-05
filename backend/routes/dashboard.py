from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_db
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
        "avg_momentum_score": (
            round(sum(d.momentum_score for d in deals) / len(deals), 1) if deals else 0
        ),
        "deals": deals,
        "approver_profiles": twins,
    }
