"""The GraphState — single shared state object for the Threshold
LangGraph StateGraph. Every node receives the current state and
returns a partial update; LangGraph merges updates according to each
field's reducer (default: overwrite; explicit: append via Annotated).

This replaces the current architecture's implicit state, which is
scattered across plain dicts passed between agents/orchestrator.py
function calls with no shared, inspectable contract.

Design choice: Pydantic BaseModel, not TypedDict.
LangGraph supports both as a state schema. We use Pydantic here
because:
  1. Runtime validation catches malformed node outputs immediately
     (e.g., a node accidentally writing a string where a list is
     expected) instead of failing silently three nodes later.
  2. Nested structures (DealInfo, ApprovalStatus, BehavioralTwinSnapshot)
     benefit from Pydantic's own validation (e.g., delay_probability
     bounded 0-1) at construction time.
  3. It matches the existing codebase's use of Pydantic-adjacent
     patterns (FastAPI request/response models) - one mental model
     for "structured data" across the whole backend.
"""

from typing import Annotated, Literal, Optional
from operator import add

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------
# Core business entities (mirror the existing SQLAlchemy models in
# models/, but as in-memory Pydantic representations for the graph run.
# The DB remains the system of record; the graph state is a working
# copy for the duration of one deal's orchestration).
# ---------------------------------------------------------------------

class DealInfo(BaseModel):
    deal_id: str
    customer_name: str
    value: float
    discount_percent: float = 0.0
    product_type: str = "standard"
    customer_segment: str = "enterprise"
    stage: str = "verbal_agreement"


class ApprovalStatus(BaseModel):
    approval_id: str
    department: str
    approver_id: str
    status: Literal["pending", "sent", "approved", "rejected", "escalated"] = "pending"
    predicted_delay_days: Optional[float] = None
    actual_delay_days: Optional[float] = None
    artifact_format_used: Optional[str] = None


class BehavioralTwinSnapshot(BaseModel):
    approver_id: str
    department: str
    avg_turnaround_days: float
    fastest_responding_format: str
    slowest_trigger: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    total_deals_reviewed: int = 0


class RiskScore(BaseModel):
    approver_id: str
    delay_probability: float = Field(ge=0.0, le=1.0)
    expected_delay_days: float
    root_cause: str
    confidence: float = Field(ge=0.0, le=1.0)


class HumanReviewDecision(BaseModel):
    """Captures the output of a Human-in-the-Loop review checkpoint."""
    action: Literal["approve", "reject", "request_changes"]
    comments: Optional[str] = None
    reviewed_by: Optional[str] = None
    timestamp: Optional[str] = None


# ---------------------------------------------------------------------
# Reducers for list/dict fields that must accumulate across parallel
# branches rather than being overwritten by whichever node finishes
# last. This is the direct fix for the current architecture's lack of
# any shared, safely-mergeable state.
# ---------------------------------------------------------------------

def merge_dicts(left: dict, right: dict) -> dict:
    """Shallow-merge two dicts; used for fields written by multiple
    parallel per-approver branches (e.g., artifacts, nudges,
    behavioral_twins) so concurrent writes don't clobber each other."""
    merged = dict(left or {})
    merged.update(right or {})
    return merged


class GraphState(BaseModel):
    # Core business entities
    deal: DealInfo
    approvals: list[ApprovalStatus] = Field(default_factory=list)
    behavioral_twins: Annotated[dict[str, BehavioralTwinSnapshot], merge_dicts] = Field(
        default_factory=dict
    )
    risk_scores: Annotated[dict[str, RiskScore], merge_dicts] = Field(default_factory=dict)
    momentum_score: int = 100

    # Drafted content (per-approver, written by parallel branches)
    artifacts: Annotated[dict[str, str], merge_dicts] = Field(default_factory=dict)
    nudges: Annotated[dict[str, str], merge_dicts] = Field(default_factory=dict)

    # Work queues — append-only across parallel branches
    pending_tasks: Annotated[list[str], add] = Field(default_factory=list)
    completed_tasks: Annotated[list[str], add] = Field(default_factory=list)

    # Human-in-the-loop
    human_decisions: Annotated[dict[str, str], merge_dicts] = Field(default_factory=dict)
    latest_review: Optional[HumanReviewDecision] = None

    # Traceability — append-only audit trail
    audit_log: Annotated[list[dict], add] = Field(default_factory=list)
    agent_outputs: Annotated[dict[str, dict], merge_dicts] = Field(default_factory=dict)

    # Control flow
    retry_count: Annotated[dict[str, int], merge_dicts] = Field(default_factory=dict)
    current_node: str = "start"

    class Config:
        arbitrary_types_allowed = True


def new_graph_state(deal: DealInfo) -> GraphState:
    """Factory for the initial state of a new deal's graph run."""
    return GraphState(
        deal=deal,
        pending_tasks=[f"process_deal:{deal.deal_id}"],
        audit_log=[{"event": "graph_started", "deal_id": deal.deal_id}],
    )
