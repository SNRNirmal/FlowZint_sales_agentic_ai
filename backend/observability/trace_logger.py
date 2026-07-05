"""Trace Logger — Custom observability hooks for LangGraph.

This module implements a LangChain AsyncCallbackHandler designed
specifically to track and log the execution lifecycle of the Threshold
StateGraph.

Responsibilities:
- Track node entry and exit.
- Measure execution duration per node.
- Count LLM calls and token usage.
- Count tool executions.
- Capture failures and retries.

By injecting this callback into the graph's config during invocation,
we gain full operational visibility into the AI reasoning process without
cluttering the business logic with telemetry code.
"""

import logging
import time
from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger("threshold.observability.trace")


class GraphTraceLogger(AsyncCallbackHandler):
    """Custom callback handler to trace LangGraph execution metrics."""

    def __init__(self):
        super().__init__()
        # State tracking for the current run
        self.node_start_times: Dict[UUID, float] = {}
        self.total_llm_calls = 0
        self.total_tokens = 0
        self.total_tool_calls = 0
        self.errors_caught = 0

    async def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Fired when a chain (or LangGraph Node) starts."""
        name = serialized.get("name", "unknown_chain")
        
        # LangGraph nodes are executed as chains under the hood
        if name != "LangGraph":
            self.node_start_times[run_id] = time.time()
            logger.debug(
                "Node execution started",
                extra={
                    "node": name,
                    "run_id": str(run_id),
                    "parent_run_id": str(parent_run_id) if parent_run_id else None
                }
            )

    async def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Fired when a chain (or LangGraph Node) completes."""
        start_time = self.node_start_times.pop(run_id, None)
        if start_time:
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                "Node execution completed",
                extra={
                    "run_id": str(run_id),
                    "duration_ms": round(duration_ms, 2)
                }
            )

    async def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Fired when a node throws an unhandled exception."""
        self.errors_caught += 1
        logger.error(
            "Node execution failed",
            extra={
                "run_id": str(run_id),
                "error": str(error)
            }
        )

    async def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Fired when an LLM call begins."""
        self.total_llm_calls += 1

    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Fired when an LLM call completes, allowing token extraction."""
        if response.llm_output and "token_usage" in response.llm_output:
            tokens = response.llm_output["token_usage"].get("total_tokens", 0)
            self.total_tokens += tokens
            
            logger.info(
                "LLM call completed",
                extra={
                    "run_id": str(run_id),
                    "tokens": tokens
                }
            )

    async def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Fired when a tool is invoked."""
        self.total_tool_calls += 1
        name = serialized.get("name", "unknown_tool")
        logger.debug(
            "Tool execution started",
            extra={
                "tool": name,
                "run_id": str(run_id)
            }
        )

    async def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Fired when a tool throws an exception."""
        self.errors_caught += 1
        logger.error(
            "Tool execution failed",
            extra={
                "run_id": str(run_id),
                "error": str(error)
            }
        )
