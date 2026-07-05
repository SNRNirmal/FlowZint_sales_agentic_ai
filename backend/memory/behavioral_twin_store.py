"""Memory-layer bridge to the existing behavioral_twins/twin_store.py.

Graph nodes (Module 4+) must never import SQLAlchemy or the models/
package directly — they go through this module, which:
  1. Wraps the existing (unchanged) read/write logic in
     behavioral_twins/twin_store.py.
  2. Converts SQLAlchemy rows into the Pydantic
     schemas.graph_state.BehavioralTwinSnapshot the graph expects.
  3. Computes the `confidence` score that Module 4's conditional
     routing (twin confidence < 0.4 -> Human Review) depends on. This
     scoring logic didn't exist in the current architecture at all —
     it's new, and lives here rather than in a node, so it's testable
     independent of any LLM call or graph wiring.

This is the "separate reasoning agents from execution/tool agents"
requirement in practice for the twin domain: the Delay Intelligence
node (a reasoning agent, Module 6) will call
`get_twin_snapshot()` and never touch the database itself.
"""

from sqlalchemy.orm import Session

from behavioral_twins.twin_store import get_twin, update_twin_after_deal
from schemas.graph_state import BehavioralTwinSnapshot

# Below this many historical deals, we don't trust the twin's averages
# enough to draft/send without a human confirming first. This constant
# is deliberately simple (not a learned model) to keep the hackathon
# build honest about what's a real prediction vs. a heuristic.
MIN_DEALS_FOR_FULL_CONFIDENCE = 20


def _compute_confidence(total_deals_reviewed: int) -> float:
    """Confidence rises linearly with historical sample size, capped
    at 1.0. An approver with 0 deals reviewed has 0 confidence, which
    Module 4's conditional edge routes straight to Human Review."""
    return round(min(1.0, total_deals_reviewed / MIN_DEALS_FOR_FULL_CONFIDENCE), 2)


def get_twin_snapshot(db: Session, approver_id: str, department: str) -> BehavioralTwinSnapshot:
    """Reads the approver's current behavioral twin (via the existing,
    unchanged twin_store.get_twin) and returns it as a typed,
    confidence-scored snapshot for the graph state.

    If no twin exists yet for this approver, returns a default profile
    with confidence=0.0 rather than raising — the graph's conditional
    routing (not this function) decides what to do about low
    confidence."""
    twin = get_twin(db, approver_id)

    if twin is None:
        return BehavioralTwinSnapshot(
            approver_id=approver_id,
            department=department,
            avg_turnaround_days=3.0,  # generic default, matches current fallback in delay_intelligence.py
            fastest_responding_format="standard summary",
            slowest_trigger="unknown",
            confidence=0.0,
            total_deals_reviewed=0,
        )

    return BehavioralTwinSnapshot(
        approver_id=twin.approver_id,
        department=twin.department,
        avg_turnaround_days=twin.avg_turnaround_days,
        fastest_responding_format=twin.fastest_responding_format,
        slowest_trigger=twin.slowest_trigger,
        confidence=_compute_confidence(twin.total_deals_reviewed),
        total_deals_reviewed=twin.total_deals_reviewed,
    )


def persist_twin_update(
    db: Session,
    approver_id: str,
    actual_delay_days: float,
    artifact_format_used: str,
) -> BehavioralTwinSnapshot:
    """Write path for the Learning node (Module 9). Delegates entirely
    to the existing update_twin_after_deal weighted-rolling-average
    logic — this module adds no new write logic, only the typed
    read-back into a BehavioralTwinSnapshot."""
    twin = update_twin_after_deal(
        db,
        approver_id=approver_id,
        actual_delay_days=actual_delay_days,
        artifact_format_used=artifact_format_used,
    )
    return get_twin_snapshot(db, approver_id, twin.department)
