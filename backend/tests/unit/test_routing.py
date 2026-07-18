"""Routing functions are pure GraphState -> str decisions. These tests
pin every branch, especially the human-review decision fan-out."""

from langgraph.graph import END

from graphs.routing import (
    route_after_approval_detection,
    route_after_delay_intelligence,
    route_after_human_review,
    route_after_twin_retrieval,
)
from schemas.graph_state import (
    ApprovalStatus,
    BehavioralTwinSnapshot,
    GraphState,
    HumanReviewDecision,
    RiskScore,
)
from tests.conftest import make_deal


def _state(**kwargs) -> GraphState:
    return GraphState(deal=make_deal(), **kwargs)


def _approval() -> ApprovalStatus:
    return ApprovalStatus(
        approval_id="ap-1", department="Finance", approver_id="finance_raj"
    )


# ---- route_after_approval_detection ----------------------------------------

def test_no_approvals_short_circuits_to_end():
    assert route_after_approval_detection(_state(approvals=[])) == END


def test_approvals_continue_to_persistence():
    assert (
        route_after_approval_detection(_state(approvals=[_approval()]))
        == "approval_persistence"
    )


# ---- route_after_human_review ----------------------------------------------

def test_approve_ends_pipeline():
    state = _state(latest_review=HumanReviewDecision(action="approve"))
    assert route_after_human_review(state) == "approval_tracking"


def test_reject_ends_pipeline():
    state = _state(latest_review=HumanReviewDecision(action="reject"))
    assert route_after_human_review(state) == "rejection_handler"


def test_request_changes_loops_back_to_document_generator():
    state = _state(latest_review=HumanReviewDecision(action="request_changes"))
    assert route_after_human_review(state) == "document_generator"


def test_missing_review_defaults_to_end():
    assert route_after_human_review(_state(latest_review=None)) == END


# ---- legacy always-continue routers (kept for future gate insertion) -------

def test_twin_retrieval_always_continues_even_with_low_confidence():
    twin = BehavioralTwinSnapshot(
        approver_id="finance_raj",
        department="Finance",
        avg_turnaround_days=3.0,
        fastest_responding_format="one-pager",
        slowest_trigger="missing context",
        confidence=0.1,
    )
    state = _state(behavioral_twins={"finance_raj": twin})
    assert route_after_twin_retrieval(state) == "delay_intelligence"


def test_delay_intelligence_always_continues_even_when_high_risk():
    risk = RiskScore(
        approver_id="finance_raj",
        delay_probability=0.95,
        expected_delay_days=9.0,
        root_cause="chronic overload",
        confidence=0.9,
    )
    state = _state(risk_scores={"finance_raj": risk})
    assert route_after_delay_intelligence(state) == "document_generator"
