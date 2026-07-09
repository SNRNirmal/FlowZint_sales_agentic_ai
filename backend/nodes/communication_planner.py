"""Communication Planner Node — Module 5, Execution Node 2.

Drafts the Slack/email nudge message for each approver, with urgency
and tone calibrated to that approver's predicted delay risk. This is
a drafting step only — the drafted message is never sent from here;
it is presented at the Human Review checkpoint (Module 6) and only
reaches Slack/Email (via tools/slack_tool.py, tools/email_tool.py)
after a human explicitly approves it in the Approval Tracker node
(Module 7).

Architecture position:
  GraphState.deal + GraphState.approvals + GraphState.risk_scores
        →  this node  →  GraphState.nudges

Design notes:
  - No DB/tool calls needed — risk_scores are already in GraphState
    from Delay Intelligence (Module 4). Pure LLM drafting, same
    "execution node" category as Document Generator.
  - Urgency threshold matches Module 4's delay_intelligence.py
    HIGH_RISK_THRESHOLD (0.7), so a deal flagged high-risk there gets
    a genuinely different (not just relabeled) drafted message here —
    this is the concrete implementation of the architecture doc's
    "IF delay > 70% -> generate escalation" conditional, expressed as
    a drafting input rather than a separate node, since urgency only
    changes tone/content, not which node runs.
  - Structured output via with_structured_output(DraftedNudge),
    replacing the current architecture's raw string response in
    agents/communication.py.
  - Per-approver drafting runs CONCURRENTLY via asyncio.gather, same
    pattern as every other Module 4/5 node.
"""

from __future__ import annotations

import asyncio
import logging

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from nodes._llm_factory import make_structured_llm
from schemas.graph_state import GraphState
from schemas.structured_outputs import DraftedNudge

logger = logging.getLogger("threshold.nodes.communication_planner")

SYSTEM_PROMPT = """You are the Communication Planner execution node \
inside Threshold. Draft a short, professional Slack message to an \
internal approver asking them to review an attached artifact. \
Calibrate tone to the urgency level given: "normal" should read as a \
routine, courteous request; "high" should convey genuine time \
sensitivity without sounding alarmist or robotic. Output only the \
message text."""

# Matches nodes/delay_intelligence.py's HIGH_RISK_THRESHOLD so a deal
# flagged high-risk there produces a genuinely escalated draft here,
# not just a relabeled one.
HIGH_RISK_THRESHOLD = 0.7

_structured_llm = None


def _get_structured_llm():
    global _structured_llm
    if _structured_llm is None:
        _structured_llm = make_structured_llm(DraftedNudge, max_tokens=200)
    return _structured_llm


class CommunicationPlanningResult(BaseModel):
    """Structured reasoning trace for this node, stored in
    GraphState.agent_outputs['communication_planner']."""

    deal_id: str
    nudges_drafted: int
    high_urgency_approvers: list[str] = Field(default_factory=list)
    failed_approvers: list[str] = Field(default_factory=list)


def _fallback_nudge(approver_id: str, department: str, deal) -> DraftedNudge:
    """Static fallback if LLM drafting fails — plain, unembellished
    request rather than a silently missing nudge."""
    message = (
        f"Hi — could you review the {department} approval for "
        f"{deal.customer_name} (${deal.value}) when you get a chance? Thanks!"
    )
    return DraftedNudge(message=message, urgency="normal", approver_id=approver_id)


async def communication_planner_node(state: GraphState, config: RunnableConfig) -> dict:
    """LangGraph execution node: Communication Planner.

    Parameters
    ----------
    state : GraphState
        Must have ``state.approvals`` and ``state.risk_scores`` populated.
    config : RunnableConfig, optional
        Unused today; accepted for signature consistency with other nodes.

    Returns
    -------
    dict
        Partial state update containing:
        - ``nudges``: dict[approver_id -> drafted message string]
        - ``audit_log``: trace entry, including which approvers got high-urgency framing
        - ``current_node``: "communication_planner"
        - ``agent_outputs``: structured reasoning result
    """
    deal = state.deal
    approvals = state.approvals
    risk_scores = state.risk_scores

    if not approvals:
        logger.info("No approvals to draft nudges for — skipping", extra={"deal_id": deal.deal_id})
        return {
            "current_node": "communication_planner",
            "audit_log": [
                {
                    "event": "communication_planning_skipped",
                    "deal_id": deal.deal_id,
                    "reason": "no approvals detected upstream",
                    "node": "communication_planner",
                }
            ],
        }

    llm = _get_structured_llm()

    async def draft_one(approval):
        risk = risk_scores.get(approval.approver_id)
        urgency = "high" if risk and risk.delay_probability > HIGH_RISK_THRESHOLD else "normal"
        root_cause = risk.root_cause if risk else "No specific delay risk identified yet."

        user_prompt = (
            f"Deal: {deal.customer_name}, ${deal.value}.\n"
            f"Department: {approval.department}.\n"
            f"Urgency: {urgency}.\n"
            f"Context / predicted friction: {root_cause}\n\n"
            f"Draft the Slack nudge message."
        )

        try:
            drafted: DraftedNudge = await llm.ainvoke(
                [("system", SYSTEM_PROMPT), ("user", user_prompt)]
            )
            return approval.approver_id, drafted, urgency, None
        except Exception as exc:
            logger.error(
                "Nudge drafting failed — using fallback message",
                extra={
                    "deal_id": deal.deal_id,
                    "approver_id": approval.approver_id,
                    "error": str(exc),
                },
            )
            return (
                approval.approver_id,
                _fallback_nudge(approval.approver_id, approval.department, deal),
                urgency,
                str(exc),
            )

    logger.info(
        "Drafting nudges concurrently",
        extra={"deal_id": deal.deal_id, "approval_count": len(approvals)},
    )

    results = await asyncio.gather(*(draft_one(a) for a in approvals), return_exceptions=True)

    nudges: dict[str, str] = {}
    high_urgency: list[str] = []
    failed: list[str] = []

    for i, item in enumerate(results):
        approver_id_for_error = approvals[i].approver_id

        if isinstance(item, Exception):
            logger.error(
                "Nudge drafting task raised an unhandled exception",
                extra={"deal_id": deal.deal_id, "approver_id": approver_id_for_error, "error": str(item)},
            )
            failed.append(approver_id_for_error)
            continue

        approver_id, drafted, urgency, error = item
        nudges[approver_id] = drafted.message
        if urgency == "high":
            high_urgency.append(approver_id)
        if error:
            failed.append(approver_id)

    result = CommunicationPlanningResult(
        deal_id=deal.deal_id,
        nudges_drafted=len(nudges),
        high_urgency_approvers=high_urgency,
        failed_approvers=failed,
    )

    audit_entry = {
        "event": "communication_planning_complete",
        "deal_id": deal.deal_id,
        "nudges_drafted": len(nudges),
        "high_urgency_approvers": high_urgency,
        "failed_approvers": failed,
        "node": "communication_planner",
    }

    logger.info(
        "Communication planning complete",
        extra={"deal_id": deal.deal_id, "nudges_drafted": len(nudges), "high_urgency": len(high_urgency)},
    )

    return {
        "nudges": nudges,
        "audit_log": [audit_entry],
        "current_node": "communication_planner",
        "agent_outputs": {"communication_planner": result.model_dump()},
    }
