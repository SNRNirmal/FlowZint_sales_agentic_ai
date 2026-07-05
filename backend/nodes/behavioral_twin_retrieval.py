"""Behavioral Twin Retrieval Node — Module 4, Reasoning Node 2.

Fetches each detected approver's Behavioral Twin profile — the core
differentiator of the whole system (see the architecture doc's
"moat" framing) — and computes which approvers have low-confidence
twins, so Module 9's conditional routing can send those specific
approvers to Human Review before any artifact is drafted for them.

Architecture position:
  GraphState.approvals  →  this node  →  GraphState.behavioral_twins
  (from Approval Detection)               (per-approver snapshots)

Design notes:
  - Calls tools.behavioral_twin_tool.get_behavioral_twin for every
    approver CONCURRENTLY via asyncio.gather — each fetch is
    independent (different approver_id, no shared mutable state
    between them), so this is the node-level parallel execution
    called out in the architecture doc's "Parallel Execution"
    section. True graph-level fan-out (separate LangGraph nodes per
    branch) is wired in Module 9; this is the node-internal
    concurrency available today without it.
  - Goes through the tool layer (Module 3), never imports
    memory/behavioral_twin_store.py directly — enforces the
    "separate reasoning from execution/tool agents" requirement
    structurally, not just by convention.
  - individual fetch failures are isolated (return_exceptions=True):
    one approver's twin-fetch exception does not fail the whole node
    or block the other approvers' results.
  - No twin found → tool already returns a confidence=0.0 default
    (see memory/behavioral_twin_store.py); this node's job is only to
    flag which approvers fall below the confidence threshold, not to
    decide what happens next — that's a conditional edge's job.
"""

from __future__ import annotations

import asyncio
import logging

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from nodes._node_utils import get_db_session
from schemas.graph_state import GraphState, BehavioralTwinSnapshot
from tools.behavioral_twin_tool import get_behavioral_twin

logger = logging.getLogger("threshold.nodes.behavioral_twin_retrieval")

# Approvers with a twin confidence below this value get flagged for
# Human Review before drafting, rather than letting the system draft
# on an under-sampled profile. Matches Module 2's confidence formula
# (total_deals_reviewed / 20, capped at 1.0).
LOW_CONFIDENCE_THRESHOLD = 0.4


class TwinRetrievalResult(BaseModel):
    """Structured reasoning trace for this node, stored in
    GraphState.agent_outputs['behavioral_twin_retrieval']."""

    deal_id: str
    twins_retrieved: int
    low_confidence_approvers: list[str] = Field(default_factory=list)
    failed_approvers: list[str] = Field(default_factory=list)


async def behavioral_twin_retrieval_node(state: GraphState, config: RunnableConfig | None = None) -> dict:
    """LangGraph reasoning node: Behavioral Twin Retrieval.

    Parameters
    ----------
    state : GraphState
        Must have ``state.approvals`` populated (by Approval Detection).
    config : RunnableConfig, optional
        Graph invocation config; expected to carry a DB session at
        ``config["configurable"]["db"]`` in production. Falls back to
        a locally-opened session for isolated unit testing.

    Returns
    -------
    dict
        Partial state update containing:
        - ``behavioral_twins``: dict[approver_id -> BehavioralTwinSnapshot]
        - ``audit_log``: trace entry, including which approvers are low-confidence
        - ``current_node``: "behavioral_twin_retrieval"
        - ``agent_outputs``: structured reasoning result
    """
    deal = state.deal
    approvals = state.approvals

    if not approvals:
        logger.info(
            "No approvals to retrieve twins for — skipping",
            extra={"deal_id": deal.deal_id},
        )
        return {
            "current_node": "behavioral_twin_retrieval",
            "audit_log": [
                {
                    "event": "twin_retrieval_skipped",
                    "deal_id": deal.deal_id,
                    "reason": "no approvals detected upstream",
                    "node": "behavioral_twin_retrieval",
                }
            ],
        }

    db, owns_session = get_db_session(config)

    try:
        async def fetch_one(approval):
            # NOTE: call .coroutine(...) directly, not .ainvoke({...}).
            # ainvoke()/invoke() build their call strictly from args_schema
            # (GetTwinInput), which deliberately excludes the InjectedToolArg
            # `db` param so an LLM would never see or try to fill it. That
            # means ainvoke() never passes `db` through to the function at
            # all -- verified via a standalone repro (see project notes) --
            # so calling the tool's underlying coroutine directly is the
            # correct way to invoke it from deterministic node code, where
            # WE are choosing to call this tool, not an LLM/agent deciding
            # to. .ainvoke()/.invoke() remain valid if this tool is ever
            # bound to an LLM agent instead, where the agent framework
            # supplies InjectedToolArg values through its own mechanism.
            result = await get_behavioral_twin.coroutine(
                approver_id=approval.approver_id,
                department=approval.department,
                db=db,
            )
            return approval.approver_id, result

        logger.info(
            "Fetching behavioral twins concurrently",
            extra={"deal_id": deal.deal_id, "approver_count": len(approvals)},
        )

        results = await asyncio.gather(
            *(fetch_one(approval) for approval in approvals),
            return_exceptions=True,
        )

        twins: dict[str, BehavioralTwinSnapshot] = {}
        low_confidence: list[str] = []
        failed: list[str] = []

        for i, item in enumerate(results):
            approver_id_for_error = approvals[i].approver_id

            if isinstance(item, Exception):
                logger.error(
                    "Twin fetch raised an exception",
                    extra={
                        "deal_id": deal.deal_id,
                        "approver_id": approver_id_for_error,
                        "error": str(item),
                    },
                )
                failed.append(approver_id_for_error)
                continue

            approver_id, tool_result = item

            if not tool_result.success or tool_result.twin is None:
                logger.warning(
                    "Twin fetch tool reported failure",
                    extra={"approver_id": approver_id, "error": tool_result.error},
                )
                failed.append(approver_id)
                continue

            twins[approver_id] = tool_result.twin
            if tool_result.twin.confidence < LOW_CONFIDENCE_THRESHOLD:
                low_confidence.append(approver_id)

        result = TwinRetrievalResult(
            deal_id=deal.deal_id,
            twins_retrieved=len(twins),
            low_confidence_approvers=low_confidence,
            failed_approvers=failed,
        )

        audit_entry = {
            "event": "behavioral_twin_retrieval_complete",
            "deal_id": deal.deal_id,
            "twins_retrieved": len(twins),
            "low_confidence_approvers": low_confidence,
            "failed_approvers": failed,
            "node": "behavioral_twin_retrieval",
        }

        if low_confidence:
            logger.info(
                "Low-confidence twins detected — Module 9 routing will send these to Human Review",
                extra={"deal_id": deal.deal_id, "approvers": low_confidence},
            )

        logger.info(
            "Behavioral twin retrieval complete",
            extra={"deal_id": deal.deal_id, "twins_retrieved": len(twins), "failed": len(failed)},
        )

        return {
            "behavioral_twins": twins,
            "audit_log": [audit_entry],
            "current_node": "behavioral_twin_retrieval",
            "agent_outputs": {"behavioral_twin_retrieval": result.model_dump()},
        }

    except Exception as exc:
        logger.error(
            "Behavioral twin retrieval failed",
            extra={"deal_id": deal.deal_id, "error": str(exc)},
            exc_info=True,
        )
        return {
            "audit_log": [
                {
                    "event": "behavioral_twin_retrieval_error",
                    "deal_id": deal.deal_id,
                    "error": str(exc),
                    "node": "behavioral_twin_retrieval",
                }
            ],
            "current_node": "behavioral_twin_retrieval",
        }
    finally:
        if owns_session:
            db.close()
