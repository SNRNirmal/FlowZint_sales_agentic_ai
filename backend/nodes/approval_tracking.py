"""Approval Tracking Node — Formalizes the execution of approved nudges.

Architecture position:
  human_review
      ↓ (Approve)
  approval_tracking  ← THIS NODE (Sends nudges, updates DB status)
      ↓
  learning

Responsibilities
----------------
- Iterates over all pending approvals in the deal.
- Extracts the drafted nudge text from `GraphState.nudges`.
- Calls `slack_tool.send_slack_nudge` to trigger the actual notification.
- Updates the database `Approval` records to "sent".
- Recalculates final momentum using `momentum_tool.compute_momentum_score`.
- Writes an audit log entry.
- Never performs AI reasoning; this is a pure execution node bridging
  the AI drafts to the real world.
"""

from __future__ import annotations

import asyncio
import logging

from langchain_core.runnables import RunnableConfig

from models.approval import Approval
from nodes._node_utils import get_db_session
from schemas.graph_state import GraphState
from tools.momentum_tool import compute_momentum_score
from tools.slack_tool import send_slack_nudge

logger = logging.getLogger("threshold.nodes.approval_tracking")


async def approval_tracking_node(state: GraphState, config: RunnableConfig) -> dict:
    """LangGraph execution node: Approval Tracking.

    Executes approved notifications and updates the corresponding DB records.

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
        - ``momentum_score``: the recalculated final score
        - ``audit_log``: execution log
        - ``current_node``: ``"approval_tracking"``
    """
    deal = state.deal
    db, owns_session = get_db_session(config)

    audit_entries = []

    try:
        logger.info(
            "Executing approved nudges via Slack tool",
            extra={"deal_id": deal.deal_id},
        )

        sent_count = 0
        for approval_status in state.approvals:
            # Only process approvals that haven't been resolved yet
            if approval_status.status not in ["pending", "escalated"]:
                continue

            approver_id = approval_status.approver_id
            department = approval_status.department
            nudge_text = state.nudges.get(approver_id)

            if not nudge_text:
                logger.warning(
                    "No nudge found for approver",
                    extra={"deal_id": deal.deal_id, "approver_id": approver_id},
                )
                continue

            # Send via slack tool directly
            channel = f"#{department.lower()}-approvals"
            result = await send_slack_nudge.coroutine(channel=channel, text=nudge_text)

            if result.success:
                logger.info(
                    "Slack nudge sent successfully",
                    extra={"deal_id": deal.deal_id, "channel": channel},
                )
                # Update DB record to "sent" synchronously via threaded SQLAlchemy
                def update_approval_status(session, app_id):
                    record = session.query(Approval).filter(Approval.id == app_id).first()
                    if record:
                        record.status = "sent"
                        session.commit()
                
                await asyncio.to_thread(update_approval_status, db, approval_status.approval_id)
                approval_status.status = "sent"
                sent_count += 1
                
                audit_entries.append({
                    "event": "nudge_sent",
                    "deal_id": deal.deal_id,
                    "approver_id": approver_id,
                    "channel": channel,
                    "node": "approval_tracking",
                })
            else:
                logger.error(
                    "Failed to send Slack nudge",
                    extra={"deal_id": deal.deal_id, "approver_id": approver_id, "error": result.error},
                )

        # Recalculate momentum score now that status has changed to 'sent'
        try:
            momentum_score = await asyncio.to_thread(
                compute_momentum_score, db, deal.deal_id
            )
            audit_entries.append({
                "event": "momentum_recalculated",
                "deal_id": deal.deal_id,
                "momentum_score": momentum_score,
                "node": "approval_tracking",
            })
        except Exception as exc:
            logger.error(
                "Momentum score recalculation failed",
                extra={"deal_id": deal.deal_id, "error": str(exc)},
            )
            momentum_score = state.momentum_score

        return {
            "momentum_score": momentum_score,
            "current_node": "approval_tracking",
            "audit_log": audit_entries,
        }

    except Exception as exc:
        logger.error(
            "approval_tracking_node raised an unhandled exception",
            extra={"deal_id": deal.deal_id, "error": str(exc)},
            exc_info=True,
        )
        return {
            "current_node": "approval_tracking",
            "audit_log": [
                {
                    "event": "approval_tracking_error",
                    "deal_id": deal.deal_id,
                    "error": str(exc),
                    "node": "approval_tracking",
                }
            ],
        }

    finally:
        if owns_session:
            db.close()
