"""Deal Service — the single entry point for processing a new deal.

Routes call process_deal_via_graph(); they do not touch the graph,
GraphState, or RunnableConfig directly.

Responsibilities:
  1. Convert the SQLAlchemy Deal ORM object to the typed DealInfo the
     graph expects.
  2. Construct the initial GraphState via new_graph_state().
  3. Build the RunnableConfig that injects the DB session and sets the
     thread_id (= deal_id, used by the checkpointer for interrupt/resume).
  4. Invoke the compiled graph asynchronously.
  5. Return the final GraphState to the caller (the route), which can
     extract whatever it needs for the HTTP response.

Error handling:
  - If the graph raises, this function propagates the exception. The
    route is responsible for converting it into an HTTP error response.
  - Individual node failures are already handled inside each node
    (see nodes/*.py — every node catches exceptions and writes to
    audit_log rather than raising). A graph-level raise here indicates
    a structural failure (e.g., checkpointer unreachable), not a
    business-logic failure.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session
from langgraph.types import Command

from graphs.builder import build_graph
from memory.checkpointer import thread_config
from models.deal import Deal
from schemas.graph_state import DealInfo, GraphState, new_graph_state

logger = logging.getLogger("threshold.services.deal_service")


def _deal_to_info(deal: Deal) -> DealInfo:
    """Convert a SQLAlchemy Deal ORM object to the typed DealInfo the
    graph expects. Pure mapping — no business logic."""
    return DealInfo(
        deal_id=deal.id,
        customer_name=deal.customer_name,
        value=deal.value,
        discount_percent=deal.discount_percent,
        product_type=deal.product_type,
        customer_segment=deal.customer_segment,
        stage=deal.stage,
    )


async def process_deal_via_graph(db: Session, deal: Deal) -> GraphState:
    """Run the full Threshold pipeline for a new deal via the LangGraph graph.

    Parameters
    ----------
    db : Session
        The SQLAlchemy session from the calling route. Injected into the
        graph's RunnableConfig so tool nodes can read/write the database
        without opening their own sessions.
    deal : Deal
        The freshly-persisted Deal ORM object.

    Returns
    -------
    GraphState
        The final state after all nodes have completed (or interrupted).
        Contains approvals, risk_scores, artifacts, nudges, and the
        full audit_log for this pipeline run.
    """
    deal_info = _deal_to_info(deal)
    initial_state = new_graph_state(deal_info)

    # thread_config sets thread_id = deal_id for the checkpointer AND
    # injects the DB session so tool nodes receive it via InjectedToolArg.
    config = thread_config(deal.id)
    config["configurable"]["db"] = db

    logger.info(
        "Invoking Threshold graph",
        extra={"deal_id": deal.id, "thread_id": deal.id},
    )

    graph = build_graph()
    final_state: GraphState = await graph.ainvoke(initial_state, config=config)

    logger.info(
        "Graph invocation complete",
        extra={
            "deal_id": deal.id,
            "approvals_count": len(final_state.approvals),
            "artifacts_count": len(final_state.artifacts),
            "nudges_count": len(final_state.nudges),
            "momentum_score": final_state.momentum_score,
        },
    )

    return final_state


async def resume_deal_graph(deal_id: str, action: str, feedback: str = "", reviewer: str = "system") -> GraphState | None:
    """Resume a paused deal graph after Human Review.

    Parameters
    ----------
    deal_id : str
        The deal ID, used as the thread_id to locate the checkpoint.
    action : str
        The reviewer's decision ("approve", "reject", "request_changes").
    feedback : str, optional
        Optional textual feedback from the reviewer.
    reviewer : str, optional
        Identifier of the reviewer.

    Returns
    -------
    GraphState | None
        The updated GraphState, or None if the graph was not paused.
    """
    config = thread_config(deal_id)
    graph = build_graph()

    # Verify the graph is actually paused. Must be aget_state: the sync
    # get_state() raises InvalidStateError when called on the event-loop
    # thread with AsyncSqliteSaver.
    state_snapshot = await graph.aget_state(config)
    if not state_snapshot.next:
        logger.warning(
            "Attempted to resume a graph that is not paused",
            extra={"deal_id": deal_id},
        )
        return None

    logger.info(
        "Resuming Threshold graph",
        extra={"deal_id": deal_id, "action": action},
    )

    resume_payload = {
        "action": action,
        "comments": feedback,
        "reviewed_by": reviewer,
    }

    # Execute the resume command
    final_state: GraphState = await graph.ainvoke(Command(resume=resume_payload), config=config)
    
    logger.info(
        "Graph resume complete",
        extra={"deal_id": deal_id},
    )
    return final_state
