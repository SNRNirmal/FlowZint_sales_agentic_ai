"""services/ — Service layer bridging API routes and the LangGraph pipeline.

Routes are thin HTTP adapters; they must not know how to build a graph,
construct a RunnableConfig, or interpret GraphState. All of that lives here.
"""
