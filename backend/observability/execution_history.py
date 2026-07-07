"""Execution History Aggregator for Observability.

This module is responsible for analyzing a graph's state history and
merging it with real-time telemetry from `trace_logger.py` to build a
unified, JSON-exportable timeline of a deal's execution.

Responsibilities:
- Reconstruct node transitions from the compiled graph's state history.
- Identify interrupt/pause and resume events.
- Aggregate tool, LLM, and token usage from the trace logger.
- Output a structured Pydantic model suitable for analytics,
  dashboards, or replay debugging.

State history access
--------------------
State history is a compiled-graph API (graph.aget_state_history), NOT a
checkpoint-saver API — AsyncSqliteSaver has no get_state_history method.
And because the checkpointer is async-only (sync methods raise), the
history must be read with the async variant, which makes
build_execution_timeline an async function.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from graphs.builder import build_graph
from memory.checkpointer import thread_config
from observability.trace_logger import GraphTraceLogger

logger = logging.getLogger("threshold.observability.history")


# ---------------------------------------------------------------------------
# Data Models for Analytics and Export
# ---------------------------------------------------------------------------

class NodeTransition(BaseModel):
    checkpoint_id: str
    node_name: str
    timestamp: str
    is_interrupt: bool = False
    is_resume: bool = False
    human_action: Optional[str] = None

class ExecutionTimeline(BaseModel):
    deal_id: str
    thread_id: str
    run_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Trace Metrics (from trace_logger.py)
    total_duration_ms: float = 0.0
    total_llm_calls: int = 0
    total_tokens: int = 0
    total_tool_calls: int = 0
    errors_caught: int = 0

    # State Metrics
    resume_count: int = 0
    final_outcome: Optional[str] = None

    # Timeline
    transitions: List[NodeTransition] = Field(default_factory=list)

    def to_json_dict(self) -> Dict[str, Any]:
        return self.model_dump()


# ---------------------------------------------------------------------------
# History Aggregation Logic
# ---------------------------------------------------------------------------

def _state_field(values: Any, key: str, default: Any = None) -> Any:
    """Read one field from a snapshot's values, which LangGraph surfaces
    either as a channel-values dict or as the GraphState model itself."""
    if isinstance(values, dict):
        return values.get(key, default)
    return getattr(values, key, default)


async def build_execution_timeline(
    deal_id: str,
    tracer: Optional[GraphTraceLogger] = None
) -> ExecutionTimeline:
    """Reconstruct a complete execution timeline for a given deal.

    Merges historical state snapshots from the compiled graph with the
    real-time telemetry captured by the trace logger during the latest run.

    Parameters
    ----------
    deal_id : str
        The deal ID, used as the thread_id.
    tracer : GraphTraceLogger, optional
        The trace logger instance from the latest graph execution, if available.
        Used to populate duration, token, and tool metrics.

    Returns
    -------
    ExecutionTimeline
        A structured, exportable timeline of the deal's lifecycle. A thread
        with no checkpoints yields an empty timeline (final_outcome None);
        "ERROR" is reserved for reconstruction failures.
    """
    timeline = ExecutionTimeline(deal_id=deal_id, thread_id=deal_id)

    # 1. Integrate Trace Metrics
    if tracer:
        timeline.total_llm_calls = tracer.total_llm_calls
        timeline.total_tokens = tracer.total_tokens
        timeline.total_tool_calls = tracer.total_tool_calls
        timeline.errors_caught = tracer.errors_caught

        # Calculate total duration based on node start times if any exist
        if tracer.node_start_times:
            earliest = min(tracer.node_start_times.values())
            timeline.total_duration_ms = (time.time() - earliest) * 1000

    # 2. Reconstruct state history from the compiled graph
    config = thread_config(deal_id)

    try:
        graph = build_graph()
        # aget_state_history yields StateSnapshots newest-first;
        # reverse for chronological order.
        history_snapshots = [snapshot async for snapshot in graph.aget_state_history(config)]
        history_snapshots.reverse()

        for snapshot in history_snapshots:
            checkpoint_id = snapshot.config.get("configurable", {}).get("checkpoint_id", "unknown")
            created_at = getattr(snapshot, "created_at", None)
            timestamp = str(created_at) if created_at else datetime.now(timezone.utc).isoformat()

            # Every node writes current_node as it completes; the initial
            # checkpoints carry the new_graph_state() default ("start").
            current_node = _state_field(snapshot.values, "current_node", "start")

            # Paused ⇔ snapshot.next is non-empty (same convention as
            # deal_service.resume_deal_graph). human_review is the only
            # interrupting node, and interrupt() suspends BEFORE the node's
            # state update is applied — so a pause shows up as human_review
            # pending in `next`, not as current_node == "human_review".
            is_interrupt = "human_review" in snapshot.next

            # A completed review lands one checkpoint later, when
            # human_review's update (latest_review + current_node) is applied.
            latest_review = _state_field(snapshot.values, "latest_review")
            is_resume = bool(latest_review) and current_node == "human_review"
            human_action = None
            if is_resume:
                human_action = latest_review.get("action") if isinstance(latest_review, dict) else getattr(latest_review, "action", None)
                timeline.resume_count += 1

            timeline.transitions.append(NodeTransition(
                checkpoint_id=checkpoint_id,
                node_name=current_node,
                timestamp=timestamp,
                is_interrupt=is_interrupt,
                is_resume=is_resume,
                human_action=human_action
            ))

        # 3. Determine final outcome from the newest snapshot
        if history_snapshots:
            last_snapshot = history_snapshots[-1]
            if not last_snapshot.next:
                timeline.final_outcome = "COMPLETED"
            elif "human_review" in last_snapshot.next:
                timeline.final_outcome = "PAUSED_PENDING_REVIEW"
            else:
                timeline.final_outcome = "IN_PROGRESS"

    except Exception as exc:
        logger.error(
            "Failed to reconstruct execution history",
            extra={"deal_id": deal_id, "error": str(exc)},
            exc_info=True
        )
        timeline.final_outcome = "ERROR"

    return timeline
