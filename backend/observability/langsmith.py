"""LangSmith Configuration & Initialization.

This module sets up the environment variables required to enable
LangSmith tracing natively within LangGraph. It is designed to be
imported early in the application lifecycle (e.g., in main.py) before
the graph is compiled or executed.

Responsibilities:
- Enable LANGCHAIN_TRACING_V2
- Set the default LANGCHAIN_PROJECT
- Verify configuration for debugging
"""

import logging
import os

logger = logging.getLogger("threshold.observability.langsmith")

def init_langsmith(project_name: str = "threshold-hitl") -> None:
    """Initialize LangSmith tracing environment variables.

    This enables automatic capturing of all graph executions, LLM calls,
    tool invocations, and state transitions without modifying the node
    code itself.

    Parameters
    ----------
    project_name : str
        The project name under which traces will be grouped in LangSmith.
    """
    # LangSmith tracing is activated natively by LangChain/LangGraph when
    # LANGCHAIN_TRACING_V2 is set to "true".
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = project_name

    # Check if the API key is present. We do not throw an error if it's
    # missing, so local development (hackathon mode) doesn't break, but
    # we emit a clear warning to observability logs.
    api_key = os.environ.get("LANGCHAIN_API_KEY")
    if not api_key:
        logger.warning(
            "LANGCHAIN_API_KEY is not set. Traces will be collected in memory "
            "but cannot be submitted to LangSmith."
        )
    else:
        logger.info(
            "LangSmith tracing enabled",
            extra={"project": project_name}
        )
