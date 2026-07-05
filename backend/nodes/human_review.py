"""Human Review Node — Pauses graph execution for HITL approval.

Architecture position:
  communication_planner
      ↓
  human_review  ← THIS NODE (interrupts execution)
      ↓ (conditional routing based on reviewer action)
  END (if Approved) or loops back to earlier nodes (if Rejected/Changes Requested)

Why this node exists
--------------------
Threshold NEVER performs external actions autonomously. Before any nudges
are sent to Slack or emails drafted, a human must review the AI's output.
This node uses LangGraph's native `interrupt()` function to suspend execution
and write the current state to the checkpointer. It will remain asleep
indefinitely until a `Command(resume=...)` is issued with the human's decision.

Design notes
------------
- Uses `langgraph.types.interrupt()` to pause. This is the official and correct
  way to implement HITL in LangGraph >= 0.2.2.
- The `interrupt()` call accepts a payload which is surfaced to the client. We
  construct a comprehensive `review_payload` here so the frontend/API doesn't
  have to query the graph state manually.
- When `Command(resume=...)` is sent by the service layer, `interrupt()` returns
  the value passed to `resume=...`. We validate it as a `HumanReviewDecision`
  and update the `GraphState.latest_review`.
- No database polling, no custom queues, no sleeping.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
import uuid

from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from schemas.graph_state import GraphState, HumanReviewDecision

logger = logging.getLogger("threshold.nodes.human_review")


def human_review_node(state: GraphState, config: RunnableConfig | None = None) -> dict:
    """LangGraph execution node: Human Review.

    Pauses the graph to wait for human review of the generated artifacts
    and communications. Resumes when a human provides a decision.

    Parameters
    ----------
    state : GraphState
        The current state containing all drafted artifacts and nudges.
    config : RunnableConfig, optional
        Standard node config.

    Returns
    -------
    dict
        Partial state update containing the reviewer's decision.
    """
    deal = state.deal

    # 1. Construct a comprehensive payload for the reviewer.
    review_payload = {
        "review_id": str(uuid.uuid4()),
        "deal_id": deal.deal_id,
        "customer_name": deal.customer_name,
        "momentum_score": state.momentum_score,
        "approvals": [
            {
                "approval_id": a.approval_id,
                "department": a.department,
                "approver_id": a.approver_id,
            }
            for a in state.approvals
        ],
        "generated_documents": state.artifacts,
        "draft_communications": state.nudges,
        "risk_scores": {
            k: {"delay_probability": v.delay_probability, "root_cause": v.root_cause}
            for k, v in state.risk_scores.items()
        },
        "behavioral_twin_summaries": {
            k: {"avg_turnaround_days": v.avg_turnaround_days, "confidence": v.confidence}
            for k, v in state.behavioral_twins.items()
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        "Pausing graph for Human Review",
        extra={"deal_id": deal.deal_id, "review_id": review_payload["review_id"]},
    )

    # 2. Suspend execution natively.
    # The graph stops here. When resumed, `action_payload` receives the data.
    action_payload = interrupt(review_payload)

    # 3. Execution resumes here after `Command(resume=...)`.
    logger.info(
        "Graph resumed from Human Review",
        extra={"deal_id": deal.deal_id, "action": action_payload.get("action")},
    )

    decision = HumanReviewDecision(
        action=action_payload.get("action", "request_changes"),
        comments=action_payload.get("comments"),
        reviewed_by=action_payload.get("reviewed_by", "system"),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    audit_entry = {
        "event": "human_review_completed",
        "deal_id": deal.deal_id,
        "action": decision.action,
        "reviewer": decision.reviewed_by,
        "node": "human_review",
    }

    return {
        "latest_review": decision,
        "current_node": "human_review",
        "audit_log": [audit_entry],
    }
