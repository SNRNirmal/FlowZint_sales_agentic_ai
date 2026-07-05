"""graphs/ — LangGraph StateGraph assembly for Threshold.

This module owns the single compiled graph for the entire backend.
Every other module (services/, routes/) gets the graph from
graphs.builder.build_graph() — nobody else compiles a StateGraph.
"""
