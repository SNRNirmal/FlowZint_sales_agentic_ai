"""Document Generator Node — Module 5, Execution Node 1.

Drafts the specific internal approval artifact for each approver,
tailored to that approver's Behavioral Twin `fastest_responding_format`
— this is the concrete "moat" behavior described throughout the
architecture doc: not a generic template, a document shaped to how
this specific person has historically responded fastest.

Architecture position:
  GraphState.deal + GraphState.approvals + GraphState.behavioral_twins
        →  this node  →  GraphState.artifacts

Design notes:
  - No DB/tool calls needed. All required data (twin profiles) is
    already in GraphState from Behavioral Twin Retrieval (Module 4) —
    this node is pure LLM drafting over in-memory state, distinct
    from the reasoning nodes (which decide facts) and the tool layer
    (which touches external systems). This is the concrete meaning of
    "execution node" vs. "reasoning node" for this specific step.
  - Structured output via with_structured_output(DraftedArtifact),
    replacing the current architecture's raw LLM string response in
    agents/document_generation.py.
  - Per-approver drafting runs CONCURRENTLY via asyncio.gather — same
    node-level parallelism pattern as Modules 4's twin retrieval and
    delay intelligence, since each approver's draft is independent.
  - `config: RunnableConfig` is accepted but unused today — reserved
    for a future Google Docs Tool call (writing the draft into a real
    shared doc), without needing to change this node's signature when
    that's added. Not built now, per "do not over-engineer" — the
    hackathon demo only needs the drafted text itself.
  - LLM failures per-approver fall back to a static template rather
    than failing the whole node, consistent with delay_intelligence.py's
    isolation pattern.
"""

from __future__ import annotations

import asyncio
import logging

from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from config import settings
from schemas.graph_state import GraphState
from schemas.structured_outputs import DraftedArtifact

logger = logging.getLogger("threshold.nodes.document_generator")

SYSTEM_PROMPT = """You are the Document Generator execution node inside \
Threshold. Draft the exact internal approval artifact requested, \
tailored to the specific format and structure this approver has \
historically responded to fastest. Be concise, concrete, and use the \
real deal numbers provided. Do not add commentary outside the \
document itself — output only the artifact content."""

_structured_llm = None


def _get_structured_llm():
    global _structured_llm
    if _structured_llm is None:
        _structured_llm = ChatAnthropic(
            model=settings.LLM_MODEL,
            api_key=settings.ANTHROPIC_API_KEY,
            max_tokens=600,
        ).with_structured_output(DraftedArtifact)
    return _structured_llm


class DocumentGenerationResult(BaseModel):
    """Structured reasoning trace for this node, stored in
    GraphState.agent_outputs['document_generator']."""

    deal_id: str
    artifacts_drafted: int
    failed_approvers: list[str] = Field(default_factory=list)


def _fallback_artifact(approver_id: str, department: str, deal) -> DraftedArtifact:
    """Static fallback used only if the LLM call fails after retries
    (LangChain's own retry inside with_structured_output is not
    configured here, so a single failure triggers this immediately —
    matching the "escalate rather than silently degrade forever"
    principle from the architecture doc's error-recovery section)."""
    content = (
        f"{department} Approval Request\n\n"
        f"Customer: {deal.customer_name}\n"
        f"Deal value: ${deal.value}\n"
        f"Discount: {deal.discount_percent}%\n"
        f"Product type: {deal.product_type}\n\n"
        f"(Automated draft unavailable — please review deal details directly.)"
    )
    return DraftedArtifact(content=content, format_used="fallback template", approver_id=approver_id)


async def document_generator_node(state: GraphState, config: RunnableConfig | None = None) -> dict:
    """LangGraph execution node: Document Generator.

    Parameters
    ----------
    state : GraphState
        Must have ``state.approvals`` and ``state.behavioral_twins`` populated.
    config : RunnableConfig, optional
        Reserved for a future Google Docs Tool call; unused today.

    Returns
    -------
    dict
        Partial state update containing:
        - ``artifacts``: dict[approver_id -> drafted content string]
        - ``audit_log``: trace entry
        - ``current_node``: "document_generator"
        - ``agent_outputs``: structured reasoning result
    """
    deal = state.deal
    approvals = state.approvals
    twins = state.behavioral_twins

    if not approvals:
        logger.info("No approvals to draft artifacts for — skipping", extra={"deal_id": deal.deal_id})
        return {
            "current_node": "document_generator",
            "audit_log": [
                {
                    "event": "document_generation_skipped",
                    "deal_id": deal.deal_id,
                    "reason": "no approvals detected upstream",
                    "node": "document_generator",
                }
            ],
        }

    llm = _get_structured_llm()

    async def draft_one(approval):
        twin = twins.get(approval.approver_id)
        preferred_format = twin.fastest_responding_format if twin else "a standard summary"

        user_prompt = (
            f"Draft a {approval.department} approval artifact for this deal:\n"
            f"- Customer: {deal.customer_name}\n"
            f"- Value: ${deal.value}\n"
            f"- Discount: {deal.discount_percent}%\n"
            f"- Product type: {deal.product_type}\n"
            f"- Customer segment: {deal.customer_segment}\n\n"
            f"This approver responds fastest to: {preferred_format}.\n"
            f"Draft the artifact in that exact style."
        )

        try:
            drafted: DraftedArtifact = await llm.ainvoke(
                [("system", SYSTEM_PROMPT), ("user", user_prompt)]
            )
            return approval.approver_id, drafted, None
        except Exception as exc:
            logger.error(
                "Document drafting failed — using fallback template",
                extra={
                    "deal_id": deal.deal_id,
                    "approver_id": approval.approver_id,
                    "error": str(exc),
                },
            )
            return approval.approver_id, _fallback_artifact(approval.approver_id, approval.department, deal), str(exc)

    logger.info(
        "Drafting artifacts concurrently",
        extra={"deal_id": deal.deal_id, "approval_count": len(approvals)},
    )

    results = await asyncio.gather(*(draft_one(a) for a in approvals), return_exceptions=True)

    artifacts: dict[str, str] = {}
    failed: list[str] = []

    for i, item in enumerate(results):
        approver_id_for_error = approvals[i].approver_id

        if isinstance(item, Exception):
            logger.error(
                "Document drafting task raised an unhandled exception",
                extra={"deal_id": deal.deal_id, "approver_id": approver_id_for_error, "error": str(item)},
            )
            failed.append(approver_id_for_error)
            continue

        approver_id, drafted, error = item
        artifacts[approver_id] = drafted.content
        if error:
            failed.append(approver_id)

    result = DocumentGenerationResult(
        deal_id=deal.deal_id,
        artifacts_drafted=len(artifacts),
        failed_approvers=failed,
    )

    audit_entry = {
        "event": "document_generation_complete",
        "deal_id": deal.deal_id,
        "artifacts_drafted": len(artifacts),
        "failed_approvers": failed,
        "node": "document_generator",
    }

    logger.info(
        "Document generation complete",
        extra={"deal_id": deal.deal_id, "artifacts_drafted": len(artifacts), "failed": len(failed)},
    )

    return {
        "artifacts": artifacts,
        "audit_log": [audit_entry],
        "current_node": "document_generator",
        "agent_outputs": {"document_generator": result.model_dump()},
    }
