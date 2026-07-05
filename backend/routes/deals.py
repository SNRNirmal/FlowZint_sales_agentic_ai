from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from models.deal import Deal
from models.approval import Approval

router = APIRouter(prefix="/deals", tags=["deals"])


@router.get("/")
def list_deals(db: Session = Depends(get_db)):
    return db.query(Deal).all()


@router.get("/{deal_id}")
def get_deal(deal_id: str, db: Session = Depends(get_db)):
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    approvals = db.query(Approval).filter(Approval.deal_id == deal_id).all()
    return {"deal": deal, "approvals": approvals}
