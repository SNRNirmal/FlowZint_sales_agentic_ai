"""Tests for observability.execution_history.build_execution_timeline.

The function was dead code that called get_state_history() on the
checkpoint SAVER — a compiled-graph method, so every call raised
AttributeError, was swallowed by the function's own try/except, and
every timeline came back final_outcome="ERROR". These tests pin the
fixed wiring: history is read from the compiled graph via the async
aget_state_history() (the AsyncSqliteSaver has no sync surface), and
the pause/resume semantics match how human_review actually interrupts.
"""

import time
import uuid

from langgraph.types import Command

import graphs.builder as builder_module
import observability.execution_history as history_module
from models.deal import Deal
from observability.execution_history import build_execution_timeline
from observability.trace_logger import GraphTraceLogger
from schemas.graph_state import new_graph_state
from tests.conftest import graph_config, make_deal, make_quiet_deal

PIPELINE_NODES = [
    "approval_detection",
    "approval_persistence",
    "behavioral_twin_retrieval",
    "delay_intelligence",
    "document_generator",
    "communication_planner",
]


async def run_big_deal_to_pause(db_session, deal_id):
    """Drive a big deal through the pipeline until it pauses at
    human_review (same setup as test_async_checkpointer.py)."""
    deal = make_deal(deal_id=deal_id)
    orm = Deal(id=deal_id, customer_name=deal.customer_name, value=deal.value,
               discount_percent=deal.discount_percent, product_type=deal.product_type,
               customer_segment=deal.customer_segment)
    db_session.add(orm)
    db_session.commit()

    graph = builder_module.build_graph()
    cfg = graph_config(deal_id, db_session)
    await graph.ainvoke(new_graph_state(deal), config=cfg)
    return graph, cfg


async def test_completed_run_yields_completed_timeline(db_session):
    """Quiet deal (no approvals) runs to END: outcome COMPLETED, real
    checkpoint ids, no interrupts, no resumes."""
    deal = make_quiet_deal(deal_id="deal-hist-quiet")
    graph = builder_module.build_graph()
    await graph.ainvoke(new_graph_state(deal), config=graph_config(deal.deal_id, db_session))

    timeline = await build_execution_timeline(deal.deal_id)

    assert timeline.final_outcome == "COMPLETED"
    assert timeline.deal_id == "deal-hist-quiet"
    assert timeline.thread_id == "deal-hist-quiet"
    assert len(timeline.transitions) >= 2
    # Chronological: the newest checkpoint is the one approval_detection wrote.
    assert timeline.transitions[-1].node_name == "approval_detection"
    assert all(t.checkpoint_id and t.checkpoint_id != "unknown" for t in timeline.transitions)
    assert not any(t.is_interrupt for t in timeline.transitions)
    assert timeline.resume_count == 0


async def test_paused_run_reports_pending_review(db_session):
    """Big deal pauses at human_review via interrupt(): the pause is
    visible as human_review pending in `next` (the node's own state
    update has NOT been applied yet), so the newest transition is the
    interrupt and the outcome is PAUSED_PENDING_REVIEW."""
    await run_big_deal_to_pause(db_session, "deal-hist-paused")

    timeline = await build_execution_timeline("deal-hist-paused")

    assert timeline.final_outcome == "PAUSED_PENDING_REVIEW"
    assert timeline.transitions[-1].is_interrupt is True
    assert timeline.transitions[-1].node_name == "communication_planner"
    assert timeline.resume_count == 0

    # The full pipeline up to the pause is reconstructed, in order.
    node_names = [t.node_name for t in timeline.transitions]
    positions = [node_names.index(n) for n in PIPELINE_NODES]
    assert positions == sorted(positions)


async def test_resumed_run_counts_resume_and_completes(db_session):
    """Approving the paused review resumes the graph to END: the review
    lands one checkpoint after the historical interrupt, carrying the
    human action; outcome flips to COMPLETED."""
    graph, cfg = await run_big_deal_to_pause(db_session, "deal-hist-resumed")
    await graph.ainvoke(
        Command(resume={"action": "approve", "comments": "ship it", "reviewed_by": "qa"}),
        config=cfg,
    )

    timeline = await build_execution_timeline("deal-hist-resumed")

    assert timeline.final_outcome == "COMPLETED"
    assert timeline.resume_count == 1
    resumes = [t for t in timeline.transitions if t.is_resume]
    assert len(resumes) == 1
    assert resumes[0].node_name == "human_review"
    assert resumes[0].human_action == "approve"
    # The historical pause point is still visible in the timeline.
    assert any(t.is_interrupt for t in timeline.transitions)


async def test_unknown_thread_yields_empty_timeline():
    """A thread with no checkpoints is an empty timeline, NOT an error —
    before the fix this path always returned final_outcome='ERROR'."""
    timeline = await build_execution_timeline("deal-never-ran")

    assert timeline.transitions == []
    assert timeline.final_outcome is None
    assert timeline.resume_count == 0


async def test_tracer_metrics_are_merged():
    """Telemetry from the trace logger is copied onto the timeline."""
    tracer = GraphTraceLogger()
    tracer.total_llm_calls = 5
    tracer.total_tokens = 1234
    tracer.total_tool_calls = 3
    tracer.errors_caught = 1
    tracer.node_start_times = {uuid.uuid4(): time.time() - 0.05}

    timeline = await build_execution_timeline("deal-hist-tracer", tracer=tracer)

    assert timeline.total_llm_calls == 5
    assert timeline.total_tokens == 1234
    assert timeline.total_tool_calls == 3
    assert timeline.errors_caught == 1
    assert timeline.total_duration_ms > 0


async def test_history_failure_yields_error_outcome(monkeypatch):
    """Reconstruction failures degrade to final_outcome='ERROR' instead
    of raising — the timeline is a dashboard artifact, not a hard path."""
    def boom():
        raise RuntimeError("graph unavailable")

    monkeypatch.setattr(history_module, "build_graph", boom)

    timeline = await build_execution_timeline("deal-hist-error")

    assert timeline.final_outcome == "ERROR"
    assert timeline.transitions == []
