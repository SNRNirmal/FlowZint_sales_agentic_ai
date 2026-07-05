"""Email Tool — execution bridge to integrations/email_client.py.

Same gating discipline as slack_tool.py: only called by the Approval
Tracker node, only after a human-approved send decision. Kept as a
separate tool (rather than folded into Slack) because departments may
prefer email over Slack, and the two channels have independent
delivery/retry characteristics worth tracing separately in LangSmith.
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

from integrations.email_client import send_email

logger = logging.getLogger("threshold.tools.email")


class EmailSendInput(BaseModel):
    to: str = Field(..., description="Recipient email address.")
    subject: str = Field(..., description="Email subject line.")
    body: str = Field(..., description="Email body, as approved by Human Review.")


class EmailSendResult(BaseModel):
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
def _send(to: str, subject: str, body: str) -> dict:
    return send_email(to, subject, body)


@tool(args_schema=EmailSendInput)
async def send_email_nudge(to: str, subject: str, body: str) -> EmailSendResult:
    """Send an approved nudge message via email.

    Mocked (console-printed) by integrations/email_client.py in the
    hackathon build; swap in a real provider there without touching
    this tool's contract.
    """
    logger.info("send_email_nudge called", extra={"to": to})

    try:
        result = await asyncio.to_thread(_send, to, subject, body)
        return EmailSendResult(success=bool(result.get("ok")), mocked=bool(result.get("mocked")))
    except Exception as exc:
        logger.error(
            "Email send failed after retries",
            extra={"to": to, "error": str(exc)},
            exc_info=True,
        )
        return EmailSendResult(success=False, error=f"Email send failed: {exc}")
