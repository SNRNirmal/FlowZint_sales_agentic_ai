"""The reducer contract every node depends on: dict fields merge,
list fields append, validation rejects malformed node output."""

import pytest
from pydantic import ValidationError

from schemas.graph_state import (
    ApprovalStatus,
    RiskScore,
    merge_dicts,
    new_graph_state,
)
from tests.conftest import make_deal


def test_merge_dicts_accumulates_and_right_wins():
    assert merge_dicts({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}
    assert merge_dicts({"a": 1}, {"a": 9}) == {"a": 9}

    left = {"a": 1}
    merged = merge_dicts(left, {"b": 2})
    assert merged is not left
    assert left == {"a": 1}  # reducer must not mutate the prior channel value


def test_merge_dicts_tolerates_none_operands():
    assert merge_dicts(None, {"a": 1}) == {"a": 1}
    assert merge_dicts({"a": 1}, None) == {"a": 1}
    assert merge_dicts(None, None) == {}


def test_merge_dicts_is_shallow_right_value_replaces_wholesale():
    assert merge_dicts({"a": {"x": 1}}, {"a": {"y": 2}}) == {"a": {"y": 2}}


def test_risk_score_probability_must_be_within_unit_interval():
    for bad in (-0.1, 1.5):
        with pytest.raises(ValidationError):
            RiskScore(
                approver_id="x",
                delay_probability=bad,
                expected_delay_days=1.0,
                root_cause="r",
                confidence=0.5,
            )
    for ok in (0.0, 1.0):
        RiskScore(
            approver_id="x",
            delay_probability=ok,
            expected_delay_days=1.0,
            root_cause="r",
            confidence=0.5,
        )


def test_approval_status_rejects_unknown_status_literal():
    with pytest.raises(ValidationError):
        ApprovalStatus(
            approval_id="ap-1",
            department="Finance",
            approver_id="finance_raj",
            status="bogus",
        )


def test_approval_status_accepts_all_known_literals():
    for status in ("pending", "sent", "approved", "rejected", "escalated"):
        ApprovalStatus(
            approval_id="ap-1",
            department="Finance",
            approver_id="finance_raj",
            status=status,
        )


def test_new_graph_state_seeds_task_queue_and_audit_log():
    state = new_graph_state(make_deal(deal_id="deal-42"))
    assert state.pending_tasks == ["process_deal:deal-42"]
    assert state.audit_log[0]["event"] == "graph_started"
    assert state.momentum_score == 100


def test_graph_state_defaults_are_empty_not_shared():
    a, b = new_graph_state(make_deal()), new_graph_state(make_deal())
    a.artifacts["x"] = "draft"
    assert b.artifacts == {}
