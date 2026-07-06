"""Approval detection is company policy encoded as rules — these tests
pin every rule boundary so a rule change is always a conscious act."""

from nodes.approval_detection import (
    APPROVAL_RULES,
    _needs_compliance,
    _needs_executive,
    _needs_finance,
    _needs_legal,
    _needs_procurement,
    _needs_security,
    approval_detection_node,
)
from schemas.graph_state import GraphState
from tests.conftest import make_deal, make_quiet_deal


# ---- Rule boundaries ------------------------------------------------------

def test_finance_fires_at_50k_value_boundary():
    assert _needs_finance(make_quiet_deal(value=50_000)) is True
    assert _needs_finance(make_quiet_deal(value=49_999.99)) is False


def test_finance_fires_at_15_percent_discount_boundary():
    assert _needs_finance(make_quiet_deal(discount_percent=15)) is True
    assert _needs_finance(make_quiet_deal(discount_percent=14.9)) is False


def test_legal_fires_on_custom_product_or_100k():
    assert _needs_legal(make_quiet_deal(product_type="custom")) is True
    assert _needs_legal(make_quiet_deal(value=100_000)) is True
    assert _needs_legal(make_quiet_deal(value=99_999, product_type="standard")) is False


def test_security_fires_only_for_enterprise_segment():
    assert _needs_security(make_quiet_deal(customer_segment="enterprise")) is True
    assert _needs_security(make_quiet_deal(customer_segment="smb")) is False


def test_procurement_needs_custom_AND_150k():
    assert _needs_procurement(make_quiet_deal(product_type="custom", value=150_000)) is True
    assert _needs_procurement(make_quiet_deal(product_type="custom", value=149_999)) is False
    assert _needs_procurement(make_quiet_deal(product_type="standard", value=200_000)) is False


def test_compliance_needs_regulated_or_custom_enterprise():
    assert _needs_compliance(make_quiet_deal(product_type="regulated", customer_segment="enterprise")) is True
    assert _needs_compliance(make_quiet_deal(product_type="custom", customer_segment="enterprise")) is True
    assert _needs_compliance(make_quiet_deal(product_type="custom", customer_segment="smb")) is False
    assert _needs_compliance(make_quiet_deal(product_type="standard", customer_segment="enterprise")) is False


def test_executive_fires_at_250k():
    assert _needs_executive(make_quiet_deal(value=250_000)) is True
    assert _needs_executive(make_quiet_deal(value=249_999)) is False


# ---- Node behavior --------------------------------------------------------

async def test_node_detects_five_departments_for_big_custom_enterprise_deal():
    state = GraphState(deal=make_deal())  # 180k, 20%, custom, enterprise
    update = await approval_detection_node(state)

    departments = [a.department for a in update["approvals"]]
    assert departments == ["Finance", "Legal", "Security", "Procurement", "Compliance"]
    assert all(a.status == "pending" for a in update["approvals"])


async def test_node_detects_all_six_for_quarter_million_deal():
    state = GraphState(deal=make_deal(value=300_000))
    update = await approval_detection_node(state)
    assert [a.department for a in update["approvals"]][-1] == "Executive"
    assert len(update["approvals"]) == 6


async def test_node_returns_empty_for_quiet_deal():
    state = GraphState(deal=make_quiet_deal())
    update = await approval_detection_node(state)
    assert update["approvals"] == []
    assert update["agent_outputs"]["approval_detection"]["total_detected"] == 0


async def test_node_queues_one_twin_retrieval_task_per_approval():
    state = GraphState(deal=make_deal())
    update = await approval_detection_node(state)
    assert update["pending_tasks"] == [
        f"retrieve_twin:{a.approver_id}" for a in update["approvals"]
    ]


# ---- Rule table wiring ----------------------------------------------------

def test_rule_table_wiring_is_pinned():
    assert [(r.department, r.approver_id, r.priority) for r in APPROVAL_RULES] == [
        ("Finance", "finance_raj", 1),
        ("Legal", "legal_jane", 2),
        ("Security", "security_amy", 3),
        ("Procurement", "procurement_li", 4),
        ("Compliance", "compliance_maria", 5),
        ("Executive", "exec_daniel", 6),
    ]
