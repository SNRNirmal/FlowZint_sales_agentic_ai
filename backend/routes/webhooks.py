"""CRM webhook route — entry point for the LangGraph pipeline.

POST /webhooks/crm receives a CRM stage-change payload, persists the
deal, and runs the full Threshold pipeline via services.deal_service.
The HTTP contract is unchanged from the legacy implementation:
  - Same path: POST /webhooks/crm
  - Same payload shape: {customer_name, value, discount_percent, ...}
  - Same response shape: {deal_id, momentum_score, drafted_actions}

The route is async because services.deal_service.process_deal_via_graph()
is async (it calls graph.ainvoke() internally).

momentum_score is read from the Deal ORM row (post-refresh) rather than
from GraphState.momentum_score: the graph nodes do not update that field
(momentum is computed as a side-effect inside tools/momentum_tool.py
which writes directly to the DB row). Reading it from the refreshed ORM
object ensures the value is always current.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_db
from models.deal import Deal
from services.deal_service import process_deal_via_graph

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/crm")
async def crm_webhook(payload: dict, db: Session = Depends(get_db)):
    """CRM stage-change webhook — creates a deal and runs the full pipeline.

    The route is the HTTP adapter only: it validates, persists the deal,
    delegates to the service layer, and formats the response. All pipeline
    logic lives in services/ and graphs/.
    """
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

    final_state = await process_deal_via_graph(db, deal)

    # Refresh the deal row to pick up any momentum_score changes written
    # directly to the DB by tools/momentum_tool.compute_momentum_score().
    # The graph's GraphState.momentum_score field is not updated by any
    # current node, so we read the authoritative value from the ORM row.
    db.refresh(deal)

    # Build the response in the same shape the legacy route returned, so
    # the frontend and any existing API consumers need no changes.
    drafted_actions = []
    for approval in final_state.approvals:
        approver_id = approval.approver_id
        risk = final_state.risk_scores.get(approver_id)
        drafted_actions.append({
            "approval_id": approval.approval_id,
            "department": approval.department,
            "approver_id": approver_id,
            "prediction": risk.model_dump() if risk is not None else {},
            "artifact_draft": final_state.artifacts.get(approver_id, ""),
            "nudge_draft": final_state.nudges.get(approver_id, ""),
            "review_status": "awaiting_human_review",
        })

    return {
        "deal_id": deal.id,
        "momentum_score": deal.momentum_score,  # Read from DB, not stale GraphState
        "drafted_actions": drafted_actions,
    }
