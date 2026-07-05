"""Execution History Aggregator for Observability.

This module is responsible for analyzing a graph's state history and
merging it with real-time telemetry from `trace_logger.py` to build a
unified, JSON-exportable timeline of a deal's execution.

Responsibilities:
- Reconstruct node transitions from the LangGraph checkpointer.
- Identify interrupt/pause and resume events.
- Aggregate tool, LLM, and token usage from the trace logger.
- Output a structured Pydantic model suitable for analytics,
  dashboards, or replay debugging.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from memory.checkpointer import get_checkpointer, thread_config
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

def build_execution_timeline(
    deal_id: str, 
    tracer: Optional[GraphTraceLogger] = None
) -> ExecutionTimeline:
    """Reconstruct a complete execution timeline for a given deal.
    
    Merges historical state snapshots from the checkpointer with the
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
        A structured, exportable timeline of the deal's lifecycle.
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

    # 2. Reconstruct checkpointer history
    checkpointer = get_checkpointer()
    config = thread_config(deal_id)
    
    try:
        # get_state_history returns an iterator of StateSnapshot objects
        # ordered from newest to oldest by default. We reverse it for chronological order.
        history_iter = checkpointer.get_state_history(config)
        history_snapshots = list(history_iter)
        history_snapshots.reverse()
        
        previous_node = None
        
        for snapshot in history_snapshots:
            state_dict = snapshot.values
            metadata = snapshot.config.get("metadata", {})
            checkpoint_id = snapshot.config.get("configurable", {}).get("checkpoint_id", "unknown")
            timestamp = snapshot.created_at if hasattr(snapshot, "created_at") else datetime.now(timezone.utc).isoformat()
            
            # The node that just finished writing this checkpoint
            # In LangGraph, tasks[0].name usually indicates the node that was executed,
            # but we can also infer it from state_dict's current_node if available.
            current_node = state_dict.get("current_node", "start")
            
            # Identify pauses
            is_interrupt = False
            is_resume = False
            human_action = None
            
            # If next is empty, the graph is paused or finished.
            if not snapshot.next and current_node == "human_review":
                is_interrupt = True
                
            # If the state has a human_review decision that wasn't in the previous node, it's a resume
            latest_review = state_dict.get("latest_review")
            if latest_review and current_node == "human_review":
                is_resume = True
                human_action = latest_review.get("action") if isinstance(latest_review, dict) else getattr(latest_review, "action", None)
                timeline.resume_count += 1
            
            transition = NodeTransition(
                checkpoint_id=checkpoint_id,
                node_name=current_node,
                timestamp=str(timestamp),
                is_interrupt=is_interrupt,
                is_resume=is_resume,
                human_action=human_action
            )
            timeline.transitions.append(transition)
            previous_node = current_node
            
        # 3. Determine final outcome
        if history_snapshots:
            last_state = history_snapshots[-1].values
            if not history_snapshots[-1].next:
                # If there are no next nodes, it's either interrupted or fully complete
                if last_state.get("current_node") == "human_review":
                    timeline.final_outcome = "PAUSED_PENDING_REVIEW"
                else:
                    timeline.final_outcome = "COMPLETED"
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
