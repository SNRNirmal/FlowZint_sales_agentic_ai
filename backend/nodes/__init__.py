"""Module 4 — Reasoning Layer.

LangGraph reasoning nodes that analyze, predict, and plan. Every node:
  - Reads GraphState (input)
  - Returns partial state updates (output)
  - Uses Structured Outputs (Pydantic v2)
  - Is async and independently testable
  - Contains zero direct I/O to external systems (CRM, Slack, Email,
    DB writes) (delegates to Tool Layer)
  - Never mutates external state directly

Note: LLM calls (e.g. delay_intelligence.py's with_structured_output)
are the reasoning itself, not "I/O" in the external-system sense above
— they don't touch the database, CRM, or messaging systems, so they
stay in the reasoning node rather than being tool-wrapped.
"""

from nodes.approval_detection import approval_detection_node
from nodes.behavioral_twin_retrieval import behavioral_twin_retrieval_node
from nodes.delay_intelligence import delay_intelligence_node
from nodes.document_generator import document_generator_node
from nodes.communication_planner import communication_planner_node

__all__ = [
    "approval_detection_node",
    "behavioral_twin_retrieval_node",
    "delay_intelligence_node",
    "document_generator_node",
    "communication_planner_node",
]
