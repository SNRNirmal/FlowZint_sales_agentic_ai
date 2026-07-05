"""Conditional edge routing functions for the Threshold StateGraph.

Every function in this module takes a GraphState and returns a string
(the name of the next node or END). LangGraph evaluates the function
after the preceding node completes and routes accordingly.

Design rules:
  - No I/O. Routing decisions are computed entirely from GraphState.
  - No side effects. These are pure decision functions.
  - Each function routes ONE specific conditional branch.
  - Function names mirror the graph node they follow, suffixed _router.
"""

from __future__ import annotations

import logging

from langgraph.graph import END

from schemas.graph_state import GraphState

logger = logging.getLogger("threshold.graphs.routing")

# Approvers below this twin-confidence value are flagged for Human Review
# before drafting, rather than letting the system draft on an under-sampled
# profile. Matches nodes/behavioral_twin_retrieval.py's LOW_CONFIDENCE_THRESHOLD.
LOW_CONFIDENCE_THRESHOLD = 0.4

# Delay probability above this value triggers escalation framing in the
# Communication Planner. Matches nodes/delay_intelligence.py's HIGH_RISK_THRESHOLD.
HIGH_RISK_THRESHOLD = 0.7


def route_after_twin_retrieval(state: GraphState) -> str:
    """After Behavioral Twin Retrieval, decide the next node.

    If ANY approver has a low-confidence twin, the graph still proceeds —
    the Delay Intelligence node handles the cold-start case via
    memory/long_term_store.get_department_pattern(). This router exists
    so that future work can insert a Human Review gate here for
    zero-history approvers without changing the builder.

    Current routing:
      always → delay_intelligence
    """
    low_confidence = [
        approver_id
        for approver_id, twin in state.behavioral_twins.items()
        if twin.confidence < LOW_CONFIDENCE_THRESHOLD
    ]

    if low_confidence:
        logger.info(
            "Low-confidence twins detected — Delay Intelligence will use org-wide fallback",
            extra={
                "deal_id": state.deal.deal_id,
                "low_confidence_approvers": low_confidence,
            },
        )

    # Always continue — cold-start handling lives in delay_intelligence_node.
    return "delay_intelligence"


def route_after_delay_intelligence(state: GraphState) -> str:
    """After Delay Intelligence, decide the next node.

    High-risk approvers get escalation framing baked into their nudge
    by the Communication Planner (which reads risk_scores). No separate
    escalation node is needed — urgency is a drafting input, not a branch.

    Current routing:
      always → document_generator
    """
    high_risk = [
        approver_id
        for approver_id, score in state.risk_scores.items()
        if score.delay_probability > HIGH_RISK_THRESHOLD
    ]

    if high_risk:
        logger.info(
            "High delay-risk approvers — escalation framing will be used in Communication Planner",
            extra={
                "deal_id": state.deal.deal_id,
                "high_risk_approvers": high_risk,
            },
        )

    return "document_generator"


def route_after_approval_detection(state: GraphState) -> str:
    """After Approval Detection, decide whether to proceed or short-circuit.

    If no approvals were detected the deal needs no internal review —
    route directly to END rather than running persistence, twin retrieval,
    delay intelligence, and drafting on an empty approvals list.

    Current routing:
      no approvals  → END
      has approvals → approval_persistence
    """
    if not state.approvals:
        logger.info(
            "No approvals detected — deal requires no internal review; ending pipeline",
            extra={"deal_id": state.deal.deal_id},
        )
        return END

    return "approval_persistence"


def route_after_human_review(state: GraphState) -> str:
    """After Human Review, route based on the human's decision.

    The graph was interrupted. When resumed, `human_review_node` stored
    the decision in `state.latest_review`. This router inspects it.

    Current routing:
      approve          → END (pipeline complete, nudges sent externally)
      reject           → END (pipeline aborted)
      request_changes  → document_generator (loop back to regenerate)
    """
    if not state.latest_review:
        logger.warning(
            "Human Review completed but no decision found; defaulting to END",
            extra={"deal_id": state.deal.deal_id},
        )
        return END

    action = state.latest_review.action

    if action == "approve":
        logger.info(
            "Human approved AI drafts — completing pipeline",
            extra={"deal_id": state.deal.deal_id},
        )
        return END
    
    if action == "reject":
        logger.info(
            "Human rejected AI drafts — pipeline aborted",
            extra={"deal_id": state.deal.deal_id},
        )
        return END

    if action == "request_changes":
        logger.info(
            "Human requested changes — looping back to Document Generator",
            extra={"deal_id": state.deal.deal_id},
        )
        return "document_generator"

    return END
