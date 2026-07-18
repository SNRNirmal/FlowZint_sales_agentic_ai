"""Approval Detection Node — Module 4, Reasoning Node 1.

Pure reasoning node that determines which internal departments must
approve a deal based on its attributes. This is the first node in
the LangGraph pipeline and defines the shape of all downstream
processing (how many parallel approval branches to spawn).

Architecture position:
  GraphState.deal  →  this node  →  GraphState.approvals
  (input)             (reason)      (output)

Design notes:
  - Rule-based, not LLM-driven. Approval routing is company policy,
    not inference. Must be deterministic, auditable, and fast.
  - No external I/O. The deal data is already in GraphState.deal —
    no CRM fetch, no DB read, no network call.
  - No tool calls. This node is pure reasoning over in-memory state.
  - Produces typed ApprovalStatus objects that integrate directly
    with the GraphState reducer contract.
  - 100% unit-testable without mocks, DB, or network.

Why rule-based instead of LLM-driven:
  1. Approval routing is policy, not prediction. "Does a $180K custom
     deal need Legal?" is a company rule, not an inference problem.
  2. Auditability. Compliance requires exact explanations for why
     each department was included. "The LLM decided" is unacceptable.
  3. Speed. This node runs on every deal — zero LLM latency.
  4. Determinism. Same deal attributes → same approvals, always.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel, Field

from schemas.graph_state import ApprovalStatus, DealInfo, GraphState

logger = logging.getLogger("threshold.nodes.approval_detection")


# -----------------------------------------------------------------------
# Structured output for this node's reasoning
# -----------------------------------------------------------------------

class DetectedApproval(BaseModel):
    """A single detected approval requirement with metadata."""

    department: str
    approver_id: str
    priority: int = Field(ge=1, description="Lower number = higher priority in the review chain")
    reason: str = Field(description="Human-readable explanation of why this department is required")
    confidence: float = Field(
        ge=0.0, le=1.0, default=1.0,
        description="Rule-based = deterministic = 1.0 confidence for every match",
    )


class ApprovalDetectionResult(BaseModel):
    """Structured output of the Approval Detection reasoning node.

    Stored in GraphState.agent_outputs['approval_detection'] so
    downstream nodes and the dashboard can inspect the reasoning
    trace without re-running the rules.
    """

    deal_id: str
    detected_approvals: list[DetectedApproval]
    total_detected: int = Field(ge=0)


# -----------------------------------------------------------------------
# Approval rules — declarative table
#
# Each rule maps a deal condition to a department + approver. Rules are
# evaluated in priority order. A rule fires if its condition returns
# True for the given deal.
#
# This is company policy encoded as code — not business logic that
# belongs in an LLM prompt. Every rule is:
#   - Deterministic (same deal → same result, always)
#   - Auditable (explicit reason string for every match)
#   - Extensible (add a new ApprovalRule entry to add a department)
#
# The condition functions are named for readability and independent
# testability — you can unit-test _needs_finance() in isolation.
# -----------------------------------------------------------------------

def _needs_finance(deal: DealInfo) -> bool:
    """Finance reviews deals ≥$50K or with discount ≥15%."""
    return deal.value >= 50_000 or deal.discount_percent >= 15


def _needs_legal(deal: DealInfo) -> bool:
    """Legal reviews custom-product deals or deals ≥$100K."""
    return deal.product_type == "custom" or deal.value >= 100_000


def _needs_security(deal: DealInfo) -> bool:
    """Security reviews all enterprise-segment deals."""
    return deal.customer_segment == "enterprise"


def _needs_procurement(deal: DealInfo) -> bool:
    """Procurement reviews custom products ≥$150K (complex sourcing)."""
    return deal.product_type == "custom" and deal.value >= 150_000


def _needs_compliance(deal: DealInfo) -> bool:
    """Compliance reviews regulated or custom enterprise deals."""
    return (
        deal.product_type in ("regulated", "custom")
        and deal.customer_segment == "enterprise"
    )


def _needs_executive(deal: DealInfo) -> bool:
    """Executive approval for deals ≥$250K."""
    return deal.value >= 250_000


@dataclass(frozen=True)
class ApprovalRule:
    """Declarative approval routing rule.

    Frozen dataclass ensures rules are immutable after construction —
    no accidental mutation during graph execution.
    """

    department: str
    approver_id: str
    priority: int
    condition: Callable[[DealInfo], bool]
    reason: str


# The rule table. Priority determines processing order downstream
# (lower number = reviewed first). The order here matches the logical
# flow: financial viability → legal risk → security posture →
# sourcing → regulatory → executive sign-off.
#
# Coupling note: approver_id strings here MUST match the approver_id keys
# in behavioral_twins/seed_data.py BOOTSTRAP_APPROVERS. If you add or rename
# an approver, update both files in lockstep — the twin retrieval node
# looks up each approver_id in the behavioral_twins table, and a mismatch
# produces a confidence=0.0 cold-start (Human Review bypass, no draft).
APPROVAL_RULES: tuple[ApprovalRule, ...] = (
    ApprovalRule(
        department="Finance",
        approver_id="finance_raj",
        priority=1,
        condition=_needs_finance,
        reason="Deal value ≥$50K or discount ≥15% requires financial review",
    ),
    ApprovalRule(
        department="Legal",
        approver_id="legal_jane",
        priority=2,
        condition=_needs_legal,
        reason="Custom product or deal value ≥$100K requires legal review",
    ),
    ApprovalRule(
        department="Security",
        approver_id="security_amy",
        priority=3,
        condition=_needs_security,
        reason="Enterprise customer segment requires security review",
    ),
    ApprovalRule(
        department="Procurement",
        approver_id="procurement_li",
        priority=4,
        condition=_needs_procurement,
        reason="Custom product ≥$150K requires procurement review for complex sourcing",
    ),
    ApprovalRule(
        department="Compliance",
        approver_id="compliance_maria",
        priority=5,
        condition=_needs_compliance,
        reason="Regulated or custom enterprise deal requires compliance review",
    ),
    ApprovalRule(
        department="Executive",
        approver_id="exec_daniel",
        priority=6,
        condition=_needs_executive,
        reason="Deal value ≥$250K requires executive approval",
    ),
)


# -----------------------------------------------------------------------
# Node function
#
# This is the async function registered as a LangGraph node via
# graph.add_node("approval_detection", approval_detection_node).
#
# Contract:
#   Input:  GraphState (reads state.deal)
#   Output: dict (partial state update merged by LangGraph reducers)
#
# The return dict keys correspond to GraphState fields:
#   - approvals: list[ApprovalStatus]     → overwrite (no reducer)
#   - audit_log: list[dict]               → add (append)
#   - pending_tasks: list[str]            → add (append)
#   - current_node: str                   → overwrite
#   - agent_outputs: dict                 → merge_dicts
# -----------------------------------------------------------------------

async def approval_detection_node(state: GraphState) -> dict:
    """LangGraph reasoning node: Approval Detection.

    Reads the deal from state, evaluates all approval rules, and
    returns a partial state update with typed ApprovalStatus objects
    for each matched rule.

    This function is pure — no DB, no network, no LLM, no tool calls.
    All inputs come from GraphState, all outputs go back to GraphState.

    Parameters
    ----------
    state : GraphState
        The current graph state. Must have ``state.deal`` populated.

    Returns
    -------
    dict
        Partial state update containing:
        - ``approvals``: list of ApprovalStatus with status="pending"
        - ``audit_log``: trace entry for this node's reasoning
        - ``pending_tasks``: downstream tasks for twin retrieval
        - ``current_node``: "approval_detection"
        - ``agent_outputs``: structured reasoning result
    """
    deal = state.deal

    logger.info(
        "Approval detection started",
        extra={
            "deal_id": deal.deal_id,
            "value": deal.value,
            "product_type": deal.product_type,
            "customer_segment": deal.customer_segment,
            "discount_percent": deal.discount_percent,
        },
    )

    try:
        # ----- Evaluate every rule against the deal -----
        detected: list[DetectedApproval] = []

        for rule in APPROVAL_RULES:
            if rule.condition(deal):
                detected.append(
                    DetectedApproval(
                        department=rule.department,
                        approver_id=rule.approver_id,
                        priority=rule.priority,
                        reason=rule.reason,
                        confidence=1.0,
                    )
                )
                logger.debug(
                    "Rule matched",
                    extra={
                        "deal_id": deal.deal_id,
                        "department": rule.department,
                        "approver_id": rule.approver_id,
                        "reason": rule.reason,
                    },
                )

        # Sort by priority (rules are already ordered, but explicit
        # sort guarantees correctness if rules are reordered later)
        detected.sort(key=lambda d: d.priority)

        # ----- Build structured reasoning output -----
        result = ApprovalDetectionResult(
            deal_id=deal.deal_id,
            detected_approvals=detected,
            total_detected=len(detected),
        )

        # ----- Convert to GraphState-compatible ApprovalStatus list -----
        # Each detected rule becomes a pending ApprovalStatus with a
        # fresh UUID. This ID is the graph's internal reference; the
        # Database Tool will create the persistent record with this
        # same ID when the downstream node calls it.
        approvals: list[ApprovalStatus] = [
            ApprovalStatus(
                approval_id=str(uuid.uuid4()),
                department=det.department,
                approver_id=det.approver_id,
                status="pending",
            )
            for det in detected
        ]

        # ----- Queue downstream work -----
        # One task per approval, telling the next node (Behavioral
        # Twin Retrieval) which approvers to look up.
        pending_tasks = [
            f"retrieve_twin:{approval.approver_id}"
            for approval in approvals
        ]

        # ----- Audit trail entry -----
        audit_entry = {
            "event": "approval_detection_complete",
            "deal_id": deal.deal_id,
            "departments_detected": [d.department for d in detected],
            "approver_ids": [d.approver_id for d in detected],
            "total_approvals": len(detected),
            "node": "approval_detection",
        }

        if not detected:
            logger.warning(
                "No approvals detected — deal may proceed without internal review",
                extra={"deal_id": deal.deal_id, "value": deal.value},
            )

        logger.info(
            "Approval detection complete",
            extra={
                "deal_id": deal.deal_id,
                "total_detected": len(detected),
                "departments": [d.department for d in detected],
            },
        )

        # ----- Return partial state update -----
        return {
            "approvals": approvals,
            "audit_log": [audit_entry],
            "pending_tasks": pending_tasks,
            "current_node": "approval_detection",
            "agent_outputs": {
                "approval_detection": result.model_dump(),
            },
        }

    except Exception as exc:
        logger.error(
            "Approval detection failed",
            extra={"deal_id": deal.deal_id, "error": str(exc)},
            exc_info=True,
        )
        raise
