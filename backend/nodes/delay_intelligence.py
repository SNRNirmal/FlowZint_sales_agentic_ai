"""Delay Intelligence Node — Module 4, Reasoning Node 3.

Predicts bottleneck risk and root cause per approver, grounded in
that approver's Behavioral Twin — the core differentiator called out
throughout the architecture doc, now expressed with LangChain's
with_structured_output() bound to schemas.structured_outputs.
DelayPrediction, replacing the current architecture's manual
json.loads() + bare except fallback in agents/delay_intelligence.py.

Architecture position:
  GraphState.deal + GraphState.behavioral_twins  →  this node  →  GraphState.risk_scores

Design notes:
  - Structured outputs via with_structured_output(DelayPrediction),
    not manual JSON parsing. LangChain handles the tool-calling
    machinery Anthropic's structured output uses under the hood;
    a malformed response raises here instead of silently producing
    an unparseable string, so the except block below is a genuine
    fallback path, not a parsing-error catch-all.
  - Runs one prediction per approver CONCURRENTLY via asyncio.gather —
    same node-level parallelism pattern as behavioral_twin_retrieval.py,
    since each approver's prediction is independent.
  - Cold-start handling: if an approver has no twin yet (confidence
    0.0, from Module 2's default), this node falls back to
    memory.long_term_store.get_department_pattern() for an org-wide
    average instead of reasoning blind. This is a direct memory-layer
    read (not tool-wrapped) because it's a read-only auxiliary lookup
    with no side effects — tool-wrapping every read would be
    over-engineering for a lookup this simple; the primary,
    stateful behavioral-twin read already goes through the tool layer
    in the previous node.
  - Per-approver LLM failures are isolated and produce a fallback
    DelayPrediction (historical average, confidence=0.3) rather than
    failing the whole node — one bad LLM response should not sink
    predictions for approvers that succeeded.
"""

from __future__ import annotations

import asyncio
import logging

from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import RunnableConfig

from config import settings
from memory.long_term_store import get_department_pattern
from nodes._node_utils import get_db_session
from schemas.graph_state import GraphState, RiskScore
from schemas.structured_outputs import DelayPrediction

logger = logging.getLogger("threshold.nodes.delay_intelligence")

SYSTEM_PROMPT = """You are the Delay Intelligence reasoning node inside \
Threshold, an internal deal-friction assistant. Given a deal and a \
specific approver's behavioral context, predict the likelihood and \
expected length of delay for this approval, and explain the root \
cause in one sentence. Ground your reasoning in the behavioral \
context provided — do not invent turnaround statistics that weren't \
given to you."""

# High delay risk threshold — Module 9's conditional edge routes
# approvers above this to a higher-urgency drafting path.
HIGH_RISK_THRESHOLD = 0.7

_structured_llm = None


def _get_structured_llm():
    """Lazily-constructed singleton so the LLM client isn't
    re-instantiated on every node call; the API key/model are static
    for the process lifetime."""
    global _structured_llm
    if _structured_llm is None:
        _structured_llm = ChatAnthropic(
            model=settings.LLM_MODEL,
            api_key=settings.ANTHROPIC_API_KEY,
            max_tokens=300,
        ).with_structured_output(DelayPrediction)
    return _structured_llm


def _build_twin_context(twin, department: str, db, deal_id: str) -> str:
    """Builds the behavioral-context string fed to the LLM. Falls
    back to the org-wide department pattern (Module 2's long-term
    memory) when no individual twin exists yet."""
    if twin is None or twin.confidence == 0.0:
        pattern = get_department_pattern(db, department)
        if pattern["org_avg_turnaround_days"] is not None:
            return (
                f"No individual behavioral twin yet for this approver. "
                f"Org-wide average turnaround for {department}: "
                f"{pattern['org_avg_turnaround_days']} days "
                f"(based on {pattern['sample_size']} past approvals)."
            )
        return (
            f"No individual behavioral twin and no org-wide history yet "
            f"for {department}. Treat this as a cold-start with wide uncertainty."
        )

    return (
        f"Approver avg turnaround: {twin.avg_turnaround_days} days. "
        f"Fastest-responding artifact format: {twin.fastest_responding_format}. "
        f"Known slow-down trigger: {twin.slowest_trigger}. "
        f"Twin confidence: {twin.confidence} (based on {twin.total_deals_reviewed} past reviews)."
    )


async def delay_intelligence_node(state: GraphState, config: RunnableConfig) -> dict:
    """LangGraph reasoning node: Delay Intelligence.

    Parameters
    ----------
    state : GraphState
        Must have ``state.approvals`` and ``state.behavioral_twins``
        populated (by Approval Detection and Behavioral Twin Retrieval).
    config : RunnableConfig, optional
        Graph invocation config carrying the DB session.

    Returns
    -------
    dict
        Partial state update containing:
        - ``risk_scores``: dict[approver_id -> RiskScore]
        - ``audit_log``: trace entry, including which approvers are high-risk
        - ``current_node``: "delay_intelligence"
        - ``agent_outputs``: structured reasoning result
    """
    deal = state.deal
    approvals = state.approvals
    twins = state.behavioral_twins

    if not approvals:
        logger.info("No approvals to predict delay for — skipping", extra={"deal_id": deal.deal_id})
        return {
            "current_node": "delay_intelligence",
            "audit_log": [
                {
                    "event": "delay_intelligence_skipped",
                    "deal_id": deal.deal_id,
                    "reason": "no approvals detected upstream",
                    "node": "delay_intelligence",
                }
            ],
        }

    db, owns_session = get_db_session(config)
    llm = _get_structured_llm()

    try:
        async def predict_one(approval):
            twin = twins.get(approval.approver_id)
            twin_context = await asyncio.to_thread(
                _build_twin_context, twin, approval.department, db, deal.deal_id
            )

            user_prompt = (
                f"Deal: value=${deal.value}, product_type={deal.product_type}, "
                f"discount_percent={deal.discount_percent}%, "
                f"customer_segment={deal.customer_segment}.\n\n"
                f"Approver: {approval.approver_id} ({approval.department}).\n"
                f"Behavioral context: {twin_context}\n\n"
                f"Predict this approval's delay risk."
            )

            try:
                prediction: DelayPrediction = await llm.ainvoke(
                    [("system", SYSTEM_PROMPT), ("user", user_prompt)]
                )
            except Exception as exc:
                logger.error(
                    "LLM structured prediction failed — using historical fallback",
                    extra={
                        "deal_id": deal.deal_id,
                        "approver_id": approval.approver_id,
                        "error": str(exc),
                    },
                )
                fallback_days = twin.avg_turnaround_days if twin else 3.0
                prediction = DelayPrediction(
                    delay_probability=0.5,
                    expected_delay_days=fallback_days,
                    root_cause="LLM prediction unavailable; used historical/org average as fallback.",
                    confidence=0.3,
                )

            return approval.approver_id, RiskScore(
                approver_id=approval.approver_id,
                delay_probability=prediction.delay_probability,
                expected_delay_days=prediction.expected_delay_days,
                root_cause=prediction.root_cause,
                confidence=prediction.confidence,
            )

        logger.info(
            "Running delay predictions concurrently",
            extra={"deal_id": deal.deal_id, "approval_count": len(approvals)},
        )

        results = await asyncio.gather(
            *(predict_one(approval) for approval in approvals),
            return_exceptions=True,
        )

        risk_scores: dict[str, RiskScore] = {}
        high_risk_approvers: list[str] = []

        for i, item in enumerate(results):
            approver_id_for_error = approvals[i].approver_id

            if isinstance(item, Exception):
                logger.error(
                    "Delay prediction task raised an unhandled exception",
                    extra={
                        "deal_id": deal.deal_id,
                        "approver_id": approver_id_for_error,
                        "error": str(item),
                    },
                )
                continue

            approver_id, score = item
            risk_scores[approver_id] = score
            if score.delay_probability > HIGH_RISK_THRESHOLD:
                high_risk_approvers.append(approver_id)

        audit_entry = {
            "event": "delay_intelligence_complete",
            "deal_id": deal.deal_id,
            "predictions_made": len(risk_scores),
            "high_risk_approvers": high_risk_approvers,
            "node": "delay_intelligence",
        }

        if high_risk_approvers:
            logger.info(
                "High delay-risk approvers detected — Module 9 routing will use escalation framing",
                extra={"deal_id": deal.deal_id, "approvers": high_risk_approvers},
            )

        logger.info(
            "Delay intelligence complete",
            extra={"deal_id": deal.deal_id, "predictions_made": len(risk_scores)},
        )

        return {
            "risk_scores": risk_scores,
            "audit_log": [audit_entry],
            "current_node": "delay_intelligence",
            "agent_outputs": {
                "delay_intelligence": {
                    "deal_id": deal.deal_id,
                    "predictions": {k: v.model_dump() for k, v in risk_scores.items()},
                    "high_risk_approvers": high_risk_approvers,
                }
            },
        }

    except Exception as exc:
        logger.error(
            "Delay intelligence node failed",
            extra={"deal_id": deal.deal_id, "error": str(exc)},
            exc_info=True,
        )
        return {
            "audit_log": [
                {
                    "event": "delay_intelligence_error",
                    "deal_id": deal.deal_id,
                    "error": str(exc),
                    "node": "delay_intelligence",
                }
            ],
            "current_node": "delay_intelligence",
        }
    finally:
        if owns_session:
            db.close()
