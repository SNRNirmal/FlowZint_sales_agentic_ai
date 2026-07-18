"""Graph builder — assembles and compiles the Threshold StateGraph.

This is the ONLY place in the codebase that calls StateGraph() and
graph.compile(). Every other module receives the compiled graph via
build_graph() — nothing else constructs a graph directly.

Pipeline sequence:
  approval_detection
      ↓ (conditional: no approvals → END, else continue)
  approval_persistence        ← writes detected approvals to the DB
      ↓
  behavioral_twin_retrieval
      ↓ (plain edge — always → delay_intelligence)
  delay_intelligence
      ↓ (plain edge — always → document_generator)
  document_generator
      ↓ (plain edge — always → communication_planner)
  communication_planner
      ↓ (plain edge — always → human_review)
  human_review
      ↓ (conditional: approve/reject → END, request_changes → document_generator)
  END

Design notes:
  - AsyncSqliteSaver checkpointer is attached at compile time. Every node's
    output is persisted to disk keyed by thread_id (= deal_id), enabling
    interrupt() / Command(resume=...) in future Human Review nodes.
  - The graph is compiled ONCE per process (singleton via _compiled_graph).
    graph.compile() is not cheap; re-compiling per-request would add
    measurable overhead and is unnecessary — the graph topology is static.
  - Pre-warmed at startup (main.py calls build_graph() in the lifespan
    handler) to eliminate the race condition on first concurrent request.
  - Only approval_detection uses a conditional edge because it has a real
    branch (no approvals → END). The other routing functions that always
    return one value are wired as plain edges — conditional edges with
    one possible destination are overhead with no benefit.
"""

from __future__ import annotations

import logging

from langgraph.graph import StateGraph, END

from graphs.routing import route_after_approval_detection, route_after_human_review
from memory.checkpointer import get_checkpointer
from nodes.approval_detection import approval_detection_node
from nodes.approval_persistence import approval_persistence_node
from nodes.behavioral_twin_retrieval import behavioral_twin_retrieval_node
from nodes.communication_planner import communication_planner_node
from nodes.delay_intelligence import delay_intelligence_node
from nodes.document_generator import document_generator_node
from nodes.human_review import human_review_node
from nodes.approval_tracking import approval_tracking_node
from nodes.learning import learning_node
from nodes.rejection_handler import rejection_handler_node
from schemas.graph_state import GraphState

logger = logging.getLogger("threshold.graphs.builder")

# Singleton compiled graph — built once on first call, reused after.
_compiled_graph = None


def build_graph():
    """Return the compiled Threshold StateGraph.

    Idempotent: the graph is built on the first call and the same compiled
    object is returned on every subsequent call. Thread-safe for reads
    (compiled graphs are immutable after compile()).

    Pre-warming this at startup (calling build_graph() in the FastAPI
    lifespan handler) eliminates the race condition where two concurrent
    requests both see _compiled_graph is None and trigger compile() twice.

    Returns
    -------
    CompiledGraph
        The fully compiled LangGraph StateGraph with checkpointing.
    """
    global _compiled_graph

    if _compiled_graph is not None:
        return _compiled_graph

    logger.info("Building Threshold StateGraph")

    graph = StateGraph(GraphState)

    # -----------------------------------------------------------------------
    # Register nodes
    # -----------------------------------------------------------------------
    graph.add_node("approval_detection", approval_detection_node)
    graph.add_node("approval_persistence", approval_persistence_node)
    graph.add_node("behavioral_twin_retrieval", behavioral_twin_retrieval_node)
    graph.add_node("delay_intelligence", delay_intelligence_node)
    graph.add_node("document_generator", document_generator_node)
    graph.add_node("communication_planner", communication_planner_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("approval_tracking", approval_tracking_node)
    graph.add_node("learning", learning_node)
    graph.add_node("rejection_handler", rejection_handler_node)

    # -----------------------------------------------------------------------
    # Entry point
    # -----------------------------------------------------------------------
    graph.set_entry_point("approval_detection")

    # -----------------------------------------------------------------------
    # Edges
    #
    # approval_detection → conditional (no approvals → END, else continue)
    #   This is the ONLY genuine branch in the current pipeline: deals that
    #   need no internal approvals short-circuit directly to END.
    #
    # All subsequent edges are plain (always-true) transitions. They were
    # previously wired as conditional edges with routing functions that
    # always returned the same single value — that pattern adds function-call
    # overhead and creates fragile one-entry path maps. Plain edges are
    # the correct primitive here.
    # -----------------------------------------------------------------------
    graph.add_conditional_edges(
        "approval_detection",
        route_after_approval_detection,
        {
            "approval_persistence": "approval_persistence",
            END: END,
        },
    )

    graph.add_edge("approval_persistence", "behavioral_twin_retrieval")
    graph.add_edge("behavioral_twin_retrieval", "delay_intelligence")
    graph.add_edge("delay_intelligence", "document_generator")
    graph.add_edge("document_generator", "communication_planner")
    graph.add_edge("communication_planner", "human_review")
    
    graph.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "approval_tracking": "approval_tracking",
            "rejection_handler": "rejection_handler",
            "document_generator": "document_generator",
            END: END,
        }
    )

    graph.add_edge("approval_tracking", "learning")
    graph.add_edge("learning", END)
    graph.add_edge("rejection_handler", END)

    # -----------------------------------------------------------------------
    # Compile with checkpointing
    # -----------------------------------------------------------------------
    checkpointer = get_checkpointer()
    _compiled_graph = graph.compile(checkpointer=checkpointer)

    logger.info("Threshold StateGraph compiled successfully")
    return _compiled_graph


def reset_for_testing() -> None:
    """Drop the compiled-graph singleton so the next build_graph() call
    recompiles (against whatever checkpointer is then active). Exists for
    the test suite; production never calls it."""
    global _compiled_graph
    _compiled_graph = None
