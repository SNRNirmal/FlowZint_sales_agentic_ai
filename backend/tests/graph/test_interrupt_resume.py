"""Interrupt/resume through the PRODUCTION service layer — the exact
code path the API routes use. This is the audit's core worry:
'resume/interrupt behavior breaks unpredictably without tests'."""

import graphs.builder as builder_module
import memory.checkpointer as checkpointer_module
from memory.checkpointer import thread_config
from models.deal import Deal
from services.deal_service import process_deal_via_graph, resume_deal_graph
from tests.conftest import as_state


async def _run_to_pause(db_session, deal_id: str) -> Deal:
    """Create a 5-approval deal and run the pipeline until it pauses
    at human_review, exactly like POST /webhooks/crm does."""
    orm = Deal(
        id=deal_id,
        customer_name="Acme Corp",
        value=180_000,
        discount_percent=20,
        product_type="custom",
        customer_segment="enterprise",
    )
    db_session.add(orm)
    db_session.commit()
    db_session.refresh(orm)
    await process_deal_via_graph(db_session, orm)
    return orm


async def _assert_not_paused(deal_id: str):
    snapshot = await builder_module.build_graph().aget_state(thread_config(deal_id))
    assert snapshot.next == ()


async def test_resume_with_approve_completes_pipeline(db_session):
    await _run_to_pause(db_session, "deal-approve")

    final = await resume_deal_graph("deal-approve", "approve", "LGTM", "sathya")

    state = as_state(final)
    assert state.latest_review is not None
    assert state.latest_review.action == "approve"
    assert state.latest_review.reviewed_by == "sathya"
    await _assert_not_paused("deal-approve")


async def test_resume_with_reject_aborts_pipeline(db_session):
    await _run_to_pause(db_session, "deal-reject")

    final = await resume_deal_graph("deal-reject", "reject", "Numbers are wrong")

    assert as_state(final).latest_review.action == "reject"
    await _assert_not_paused("deal-reject")


async def test_request_changes_regenerates_and_pauses_again(db_session, mock_llms):
    await _run_to_pause(db_session, "deal-loop")
    drafts_before = len(mock_llms["docs"].calls)  # 5

    await resume_deal_graph("deal-loop", "request_changes", "Make it shorter")

    # Looped back through document_generator → drafted 5 more artifacts…
    assert len(mock_llms["docs"].calls) == drafts_before + 5
    # …and is now paused at human_review for a SECOND review.
    snapshot = await builder_module.build_graph().aget_state(thread_config("deal-loop"))
    assert snapshot.next == ("human_review",)

    # Second review approves — pipeline completes.
    final = await resume_deal_graph("deal-loop", "approve")
    assert as_state(final).latest_review.action == "approve"
    await _assert_not_paused("deal-loop")


async def test_resume_of_never_paused_deal_returns_none(db_session):
    result = await resume_deal_graph("deal-that-never-ran", "approve")
    assert result is None


async def test_paused_review_survives_process_restart(db_session):
    """Interrupt, then simulate a full process restart (drop the compiled
    graph AND close the checkpointer connection), then re-init from the same
    checkpoint file — exactly what a new process's lifespan does — and resume.
    Proves paused reviews are durable."""
    await _run_to_pause(db_session, "deal-restart")

    # Simulate restart: compiled graph dropped, connection closed. The
    # CHECKPOINT_DB_PATH env still points at the same tmp file.
    builder_module.reset_for_testing()
    await checkpointer_module.aclose_checkpointer()

    # New process boots: lifespan re-inits the checkpointer, the graph
    # rebuilds on demand and finds the checkpoint on disk.
    await checkpointer_module.ainit_checkpointer()
    snapshot = await builder_module.build_graph().aget_state(thread_config("deal-restart"))
    assert snapshot.next == ("human_review",)

    final = await resume_deal_graph("deal-restart", "approve", reviewer="post-restart")
    assert as_state(final).latest_review.action == "approve"
    await _assert_not_paused("deal-restart")
