"""Rejection Handler Node — Gracefully aborts a rejected deal.

Architecture position:
  human_review
      ↓ (Reject)
  rejection_handler  ← THIS NODE (Updates deal status)
      ↓
  END

Responsibilities
----------------
- Updates the `deals` table to mark the deal as rejected.
- Appends to the audit_log.
"""

from __future__ import annotations

import asyncio
import logging

from langchain_core.runnables import RunnableConfig

from nodes._node_utils import get_db_session
from schemas.graph_state import GraphState
from models.deal import Deal

logger = logging.getLogger("threshold.nodes.rejection_handler")


async def rejection_handler_node(state: GraphState, config: RunnableConfig) -> dict:
    """LangGraph execution node: Rejection Handler.

    Marks the deal as rejected following human review.

    Parameters
    ----------
    state : GraphState
        The current state containing the deal.
    config : RunnableConfig, optional
        Expected to carry a DB session at ``config["configurable"]["db"]``.

    Returns
    -------
    dict
        Partial state update containing:
        - ``current_node``: ``"rejection_handler"``
        - ``audit_log``: execution log
    """
    deal = state.deal
    db, owns_session = get_db_session(config)

    audit_entries = []

    try:
        logger.info(
            "Handling rejected deal",
            extra={"deal_id": deal.deal_id},
        )

        def update_deal_status(session, d_id):
            record = session.query(Deal).filter(Deal.id == d_id).first()
            if record:
                record.status = "rejected"
                session.commit()

        await asyncio.to_thread(update_deal_status, db, deal.deal_id)

        audit_entries.append({
            "event": "deal_rejected",
            "deal_id": deal.deal_id,
            "node": "rejection_handler",
            "message": "Deal rejected by human reviewer."
        })

        return {
            "current_node": "rejection_handler",
            "audit_log": audit_entries,
        }

    except Exception as exc:
        logger.error(
            "rejection_handler_node raised an unhandled exception",
            extra={"deal_id": deal.deal_id, "error": str(exc)},
            exc_info=True,
        )
        raise

    finally:
        if owns_session:
            db.close()
