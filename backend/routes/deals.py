from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from models.deal import Deal
from models.deal_job import DealJob
from models.approval import Approval
from observability.execution_history import build_execution_timeline
from memory.checkpointer import thread_config
from graphs.builder import build_graph
from services.deal_service import ensure_graph_state

router = APIRouter(prefix="/deals", tags=["deals"])


@router.get("/")
def list_deals(db: Session = Depends(get_db)):
    return db.query(Deal).all()


@router.get("/{deal_id}/status")
def get_deal_status(deal_id: str, db: Session = Depends(get_db)):
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    job = db.query(DealJob).filter(DealJob.deal_id == deal_id).first()
    if not job:
        return {
            "deal_id": deal_id,
            "status": "pending",
            "current_node": None,
            "progress": 0,
            "error": None,
            "started_at": None,
            "finished_at": None,
        }

    return {
        "deal_id": deal_id,
        "status": job.pipeline_status,
        "current_node": job.current_node,
        "progress": job.progress,
        "error": job.error,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


@router.get("/{deal_id}")
def get_deal(deal_id: str, db: Session = Depends(get_db)):
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    approvals = db.query(Approval).filter(Approval.deal_id == deal_id).all()
    return {"deal": deal, "approvals": approvals}


@router.get("/{deal_id}/result")
async def get_deal_result(deal_id: str, db: Session = Depends(get_db)):
    """Fetch the result payload that was previously returned synchronously by POST /webhooks/crm."""
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    config = thread_config(deal_id)
    graph = build_graph()
    
    state_snapshot = await graph.aget_state(config)
    if not state_snapshot or not state_snapshot.values:
        raise HTTPException(status_code=404, detail="Graph state not found for deal")

    final_state = ensure_graph_state(state_snapshot.values)

    drafted_actions = []
    for approval in final_state.approvals:
        approver_id = approval.approver_id
        risk = final_state.risk_scores.get(approver_id)
        agent_meta = final_state.agent_outputs.get(approver_id, {})
        risk_meta = risk.metadata if risk and hasattr(risk, "metadata") else {}
        
        # Merge metadata, defaulting to llm_available=True if no fallback was used
        metadata = {"llm_available": True, "generated_by": "llm"}
        if "llm_available" in risk_meta or "llm_available" in agent_meta:
            # If ANY node used fallback, mark the whole action as fallback
            is_fallback = not risk_meta.get("llm_available", True) or not agent_meta.get("llm_available", True)
            metadata["llm_available"] = not is_fallback
            metadata["generated_by"] = "fallback" if is_fallback else "llm"

        drafted_actions.append({
            "approval_id": approval.approval_id,
            "department": approval.department,
            "approver_id": approver_id,
            "prediction": risk.model_dump() if risk is not None else {},
            "artifact_draft": final_state.artifacts.get(approver_id, ""),
            "nudge_draft": final_state.nudges.get(approver_id, ""),
            "metadata": metadata,
            "review_status": "awaiting_human_review",
        })

    return {
        "deal_id": deal.id,
        "momentum_score": deal.momentum_score,
        "drafted_actions": drafted_actions,
    }


@router.get("/{deal_id}/timeline")
async def get_deal_timeline(deal_id: str, db: Session = Depends(get_db)):
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    timeline = await build_execution_timeline(deal_id)
    return timeline.model_dump()
