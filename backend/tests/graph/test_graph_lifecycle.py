"""Runs the REAL compiled graph (real checkpointer on tmp_path, real
in-memory DB, fake LLMs) through its two macro paths: short-circuit
and full-run-to-interrupt."""

import graphs.builder as builder_module
from models.approval import Approval
from models.deal import Deal
from schemas.graph_state import new_graph_state
from tests.conftest import as_state, graph_config, make_deal, make_quiet_deal
from tools.momentum_tool import WEIGHTS

FIVE_APPROVERS = {
    "finance_raj",
    "legal_jane",
    "security_amy",
    "procurement_li",
    "compliance_maria",
}


def _persist_orm_deal(db_session, deal_info) -> Deal:
    orm = Deal(
        id=deal_info.deal_id,
        customer_name=deal_info.customer_name,
        value=deal_info.value,
        discount_percent=deal_info.discount_percent,
        product_type=deal_info.product_type,
        customer_segment=deal_info.customer_segment,
        stage=deal_info.stage,
    )
    db_session.add(orm)
    db_session.commit()
    db_session.refresh(orm)
    return orm


# ---- Short-circuit path -----------------------------------------------------

async def test_quiet_deal_short_circuits_to_end(db_session, mock_llms):
    deal = make_quiet_deal()
    graph = builder_module.build_graph()
    config = graph_config(deal.deal_id, db_session)

    result = await graph.ainvoke(new_graph_state(deal), config=config)
    state = as_state(result)

    assert state.approvals == []
    snapshot = await graph.aget_state(config)
    assert snapshot.next == ()  # ran to END — not paused


async def test_quiet_deal_never_touches_llms_or_db(db_session, mock_llms):
    deal = make_quiet_deal()
    graph = builder_module.build_graph()
    await graph.ainvoke(new_graph_state(deal), config=graph_config(deal.deal_id, db_session))

    assert mock_llms["delay"].calls == []
    assert mock_llms["docs"].calls == []
    assert mock_llms["nudges"].calls == []
    assert db_session.query(Approval).count() == 0


# ---- Full path to interrupt -------------------------------------------------

async def test_big_deal_pauses_at_human_review(db_session):
    deal = make_deal(deal_id="deal-big")
    _persist_orm_deal(db_session, deal)
    graph = builder_module.build_graph()
    config = graph_config("deal-big", db_session)

    await graph.ainvoke(new_graph_state(deal), config=config)

    snapshot = await graph.aget_state(config)
    assert snapshot.next == ("human_review",)


async def test_interrupt_payload_carries_everything_the_reviewer_needs(db_session):
    deal = make_deal(deal_id="deal-payload")
    _persist_orm_deal(db_session, deal)
    graph = builder_module.build_graph()
    config = graph_config("deal-payload", db_session)

    await graph.ainvoke(new_graph_state(deal), config=config)

    snapshot = await graph.aget_state(config)
    payload = snapshot.tasks[0].interrupts[0].value
    assert payload["deal_id"] == "deal-payload"
    assert {"review_id", "customer_name", "momentum_score", "behavioral_twin_summaries", "timestamp"} <= payload.keys()
    assert set(payload["generated_documents"]) == FIVE_APPROVERS
    assert set(payload["draft_communications"]) == FIVE_APPROVERS
    assert set(payload["risk_scores"]) == FIVE_APPROVERS
    assert len(payload["approvals"]) == 5
    assert {a["approver_id"] for a in payload["approvals"]} == FIVE_APPROVERS


async def test_big_deal_persists_approvals_and_momentum(db_session):
    deal = make_deal(deal_id="deal-momentum")
    orm = _persist_orm_deal(db_session, deal)
    graph = builder_module.build_graph()
    config = graph_config("deal-momentum", db_session)

    result = await graph.ainvoke(new_graph_state(deal), config=config)
    state = as_state(result)

    rows = db_session.query(Approval).filter_by(deal_id="deal-momentum").all()
    assert len(rows) == 5
    assert {r.approver_id for r in rows} == FIVE_APPROVERS
    assert all(r.status == "pending" for r in rows)

    db_session.refresh(orm)
    assert orm.momentum_score == 100 - 5 * WEIGHTS["pending_approval"]
    assert state.momentum_score == orm.momentum_score  # state and DB in sync


async def test_each_llm_called_once_per_approver(db_session, mock_llms):
    deal = make_deal(deal_id="deal-calls")
    _persist_orm_deal(db_session, deal)
    graph = builder_module.build_graph()
    await graph.ainvoke(new_graph_state(deal), config=graph_config("deal-calls", db_session))

    assert len(mock_llms["delay"].calls) == 5
    assert len(mock_llms["docs"].calls) == 5
    assert len(mock_llms["nudges"].calls) == 5


async def test_full_run_populates_all_behavioral_twins(db_session):
    """Direct pin on the behavioral_twin_retrieval half of the Task 6.5
    race fix: every approver gets a twin snapshot, none dropped."""
    deal = make_deal(deal_id="deal-twins")
    _persist_orm_deal(db_session, deal)
    graph = builder_module.build_graph()

    result = await graph.ainvoke(new_graph_state(deal), config=graph_config("deal-twins", db_session))
    state = as_state(result)

    assert set(state.behavioral_twins) == FIVE_APPROVERS
    twin_output = state.agent_outputs["behavioral_twin_retrieval"]
    assert twin_output["failed_approvers"] == []
