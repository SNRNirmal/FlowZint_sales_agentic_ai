"""Slack Tool — execution bridge to integrations/slack_client.py.

This tool is only ever invoked by the Approval Tracker node (Module 7),
and only after the Human Review node's interrupt() has resumed with an
"approve" decision. It performs no gating itself — that discipline
lives in the graph's conditional edges (Module 4/9) — but it exists as
a distinct tool so that constraint is visible and auditable: nothing
in this codebase can send a Slack message except through this one
function, which is called from exactly one place in the compiled graph.
"""

from __future__ import annotations

import asyncio
import logging

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from integrations.slack_client import send_slack_message

logger = logging.getLogger("threshold.tools.slack")


class SlackSendInput(BaseModel):
    channel: str = Field(..., description="Slack channel to post to, e.g. '#legal-approvals'.")
    text: str = Field(..., description="The message text to send, as approved by Human Review.")


class SlackSendResult(BaseModel):
    success: bool
    mocked: bool = False
    error: str | None = None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _send(channel: str, text: str) -> dict:
    return send_slack_message(channel, text)


@tool(args_schema=SlackSendInput)
async def send_slack_nudge(channel: str, text: str) -> SlackSendResult:
    """Send an approved nudge message to Slack.

    Falls back to a console-mocked send (via integrations/slack_client.py)
    if no SLACK_BOT_TOKEN is configured, so this tool works unmodified
    in the hackathon demo environment.
    """
    logger.info("send_slack_nudge called", extra={"channel": channel})

    try:
        result = await asyncio.to_thread(_send, channel, text)
        return SlackSendResult(success=bool(result.get("ok")), mocked=bool(result.get("mocked")))
    except Exception as exc:
        logger.error(
            "Slack send failed after retries",
            extra={"channel": channel, "error": str(exc)},
            exc_info=True,
        )
        return SlackSendResult(success=False, error=f"Slack send failed: {exc}")
