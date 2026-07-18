"""Learning Node — Closes the execution loop by persisting feedback.

Architecture position:
  approval_tracking
      ↓
  learning  ← THIS NODE (Updates twins, logs feedback)
      ↓
  END

Responsibilities
----------------
- Iterates over all approvals in the deal.
- Uses `record_outcome_sync` to persist twin updates and learning logs.
- Appends to the audit_log.
"""

from __future__ import annotations

import asyncio
import logging

from langchain_core.runnables import RunnableConfig

from nodes._node_utils import get_db_session
from schemas.graph_state import GraphState
from tools.learning_tool import record_outcome_sync
from memory.behavioral_twin_store import get_twin_snapshot

logger = logging.getLogger("threshold.nodes.learning")


async def learning_node(state: GraphState, config: RunnableConfig) -> dict:
    """LangGraph execution node: Learning.

    Persists feedback after approvals complete.

    Parameters
    ----------
    state : GraphState
        The current state containing all drafted nudges and the latest human review.
    config : RunnableConfig, optional
        Expected to carry a DB session at ``config["configurable"]["db"]``.

    Returns
    -------
    dict
        Partial state update containing:
        - ``current_node``: ``"learning"``
        - ``audit_log``: execution log
        - ``behavioral_twins``: updated twin snapshots
    """
    deal = state.deal
    db, owns_session = get_db_session(config)

    audit_entries = []
    updated_twins = {}

    try:
        logger.info(
            "Executing learning cycle",
            extra={"deal_id": deal.deal_id},
        )

        for approval_status in state.approvals:
            # We record outcomes for all sent/approved approvals
            if approval_status.status not in ["sent", "approved"]:
                continue

            approver_id = approval_status.approver_id
            
            # Use actual delay if provided, else fallback to predicted or default
            actual_delay = approval_status.actual_delay_days
            if actual_delay is None:
                actual_delay = approval_status.predicted_delay_days or 1.0
                
            format_used = approval_status.artifact_format_used or "standard summary"
            reason = getattr(state.latest_review, "comments", "") or "Approved by human reviewer"

            try:
                # Update DB
                await asyncio.to_thread(
                    record_outcome_sync,
                    db,
                    deal.deal_id,
                    approver_id,
                    actual_delay,
                    format_used,
                    reason,
                )
                
                # Fetch updated twin for state
                twin_snapshot = await asyncio.to_thread(
                    get_twin_snapshot, db, approver_id, approval_status.department
                )
                updated_twins[approver_id] = twin_snapshot
                
                audit_entries.append({
                    "event": "behavioral_twin_updated",
                    "deal_id": deal.deal_id,
                    "approver_id": approver_id,
                    "node": "learning",
                    "message": "Behavioral twin updated."
                })
            except Exception as e:
                logger.warning(
                    f"Failed to record learning outcome for approver {approver_id}: {e}",
                    extra={"deal_id": deal.deal_id, "approver_id": approver_id},
                )

        audit_entries.append({
            "event": "learning_cycle_completed",
            "deal_id": deal.deal_id,
            "node": "learning",
            "message": "Learning cycle completed."
        })
        
        audit_entries.append({
            "event": "approval_feedback_persisted",
            "deal_id": deal.deal_id,
            "node": "learning",
            "message": "Approval feedback persisted."
        })

        return {
            "current_node": "learning",
            "audit_log": audit_entries,
            "behavioral_twins": updated_twins,
        }

    except Exception as exc:
        logger.error(
            "learning_node raised an unhandled exception",
            extra={"deal_id": deal.deal_id, "error": str(exc)},
            exc_info=True,
        )
        raise

    finally:
        if owns_session:
            db.close()
