"""Regression tests for the AsyncSqliteSaver swap (Task 6.5).

Bug 1: sync SqliteSaver raised NotImplementedError on graph.ainvoke().
Bug 2: concurrent to_thread DB reads over one session dropped approvers.
"""

import graphs.builder as builder_module
from schemas.graph_state import new_graph_state
from tests.conftest import as_state, graph_config, make_deal, make_quiet_deal


async def test_graph_ainvoke_works_with_async_checkpointer(db_session):
    """Quiet deal runs to END through the real checkpointer — the exact
    call that raised NotImplementedError with the sync SqliteSaver."""
    deal = make_quiet_deal()
    graph = builder_module.build_graph()
    result = await graph.ainvoke(new_graph_state(deal), config=graph_config(deal.deal_id, db_session))
    assert as_state(result).approvals == []


async def test_full_pipeline_drafts_for_every_approver(db_session, mock_llms):
    """Big deal reaches human_review with ALL FIVE approvers processed —
    the assertion that was ~50% flaky under the shared-session race."""
    from models.deal import Deal

    deal = make_deal(deal_id="deal-race")
    orm = Deal(id="deal-race", customer_name=deal.customer_name, value=deal.value,
               discount_percent=deal.discount_percent, product_type=deal.product_type,
               customer_segment=deal.customer_segment)
    db_session.add(orm)
    db_session.commit()

    graph = builder_module.build_graph()
    result = await graph.ainvoke(new_graph_state(deal), config=graph_config("deal-race", db_session))
    state = as_state(result)

    assert len(mock_llms["delay"].calls) == 5
    assert len(mock_llms["docs"].calls) == 5
    assert len(mock_llms["nudges"].calls) == 5
    assert len(state.risk_scores) == 5
