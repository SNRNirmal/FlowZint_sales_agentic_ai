import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_db
from models.deal import Deal
from agents.orchestrator import process_new_deal

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/crm")
def crm_webhook(payload: dict, db: Session = Depends(get_db)):
    """Simulates a CRM stage-change webhook that creates a new deal and
    immediately kicks off the Orchestrator pipeline."""

    deal = Deal(
        id=str(uuid.uuid4()),
        customer_name=payload["customer_name"],
        value=payload["value"],
        discount_percent=payload.get("discount_percent", 0),
        product_type=payload.get("product_type", "standard"),
        customer_segment=payload.get("customer_segment", "enterprise"),
        stage=payload.get("stage", "verbal_agreement"),
    )
    db.add(deal)
    db.commit()
    db.refresh(deal)

    drafted_actions = process_new_deal(db, deal)

    return {
        "deal_id": deal.id,
        "momentum_score": deal.momentum_score,
        "drafted_actions": drafted_actions,
    }
