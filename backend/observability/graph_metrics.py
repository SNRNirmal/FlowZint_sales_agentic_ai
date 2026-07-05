"""Graph Metrics — Analytics and Visualization Engine.

This module computes system-wide, aggregated analytics by consuming
batches of ExecutionTimeline objects. It provides high-level health
and performance metrics for dashboards without duplicating the
low-level tracing logic.

Responsibilities:
- Compute average performance metrics (durations, tokens, tool calls).
- Calculate workflow frequencies (interrupts, resumes, errors).
- Calculate business outcomes (approval/rejection rates).
- Generate automatic Mermaid graph visualizations.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

from graphs.builder import build_graph
from observability.execution_history import ExecutionTimeline


class AggregatedMetrics(BaseModel):
    """Encapsulates system-wide graph performance and business metrics."""
    
    # Volume Metrics
    total_graph_executions: int = 0
    checkpoint_count: int = 0
    
    # Performance Averages
    average_execution_duration_ms: float = 0.0
    average_node_duration_ms: float = 0.0
    average_llm_tokens: float = 0.0
    average_tool_calls: float = 0.0
    
    # Workflow Frequencies
    interrupt_frequency: float = 0.0
    resume_frequency: float = 0.0
    error_rate: float = 0.0
    
    # Business Rates (based on Human Review actions)
    approval_rate: float = 0.0
    rejection_rate: float = 0.0
    request_changes_rate: float = 0.0


def compute_aggregated_metrics(timelines: List[ExecutionTimeline]) -> AggregatedMetrics:
    """Compute high-level analytics from a batch of execution timelines.
    
    Parameters
    ----------
    timelines : List[ExecutionTimeline]
        A collection of deal execution histories.
        
    Returns
    -------
    AggregatedMetrics
        Calculated KPIs suitable for dashboard display.
    """
    total_executions = len(timelines)
    if total_executions == 0:
        return AggregatedMetrics()

    metrics = AggregatedMetrics(total_graph_executions=total_executions)
    
    total_duration = 0.0
    total_tokens = 0
    total_tools = 0
    total_errors = 0
    total_interrupts = 0
    total_resumes = 0
    
    # Human actions counting
    action_counts = {"approve": 0, "reject": 0, "request_changes": 0}
    total_human_actions = 0

    for tl in timelines:
        total_duration += tl.total_duration_ms
        total_tokens += tl.total_tokens
        total_tools += tl.total_tool_calls
        if tl.errors_caught > 0:
            total_errors += 1
            
        metrics.checkpoint_count += len(tl.transitions)
        
        has_interrupt = False
        for transition in tl.transitions:
            if transition.is_interrupt:
                has_interrupt = True
            if transition.is_resume:
                total_resumes += 1
            if transition.human_action:
                action = transition.human_action.lower()
                if action in action_counts:
                    action_counts[action] += 1
                total_human_actions += 1
                
        if has_interrupt:
            total_interrupts += 1

    # Calculate averages and rates
    metrics.average_execution_duration_ms = total_duration / total_executions
    
    if metrics.checkpoint_count > 0:
        metrics.average_node_duration_ms = total_duration / metrics.checkpoint_count
        
    metrics.average_llm_tokens = total_tokens / total_executions
    metrics.average_tool_calls = total_tools / total_executions
    
    metrics.interrupt_frequency = total_interrupts / total_executions
    metrics.resume_frequency = total_resumes / total_executions
    metrics.error_rate = total_errors / total_executions
    
    if total_human_actions > 0:
        metrics.approval_rate = action_counts["approve"] / total_human_actions
        metrics.rejection_rate = action_counts["reject"] / total_human_actions
        metrics.request_changes_rate = action_counts["request_changes"] / total_human_actions

    return metrics


def generate_mermaid_visualization() -> str:
    """Extract the compiled graph and return its Mermaid representation.
    
    This function bridges the LangGraph structure to frontend visualizers
    and architecture documentation automatically.
    
    Returns
    -------
    str
        The mermaid diagram syntax representing the current pipeline.
    """
    graph = build_graph()
    
    try:
        # LangGraph exposes a .get_graph() method which wraps the compiled graph
        # into a Graph object capable of drawing itself via mermaid syntax.
        return graph.get_graph().draw_mermaid()
    except Exception:
        return "graph TD;\n    Error-->GenerationFailed;"
