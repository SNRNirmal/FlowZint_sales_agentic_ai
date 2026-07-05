"""Communication Agent — drafts the Slack/email nudge. Tone/urgency
calibrated to delay risk. Output always goes through the Human Review
Checkpoint before it is actually sent (see routes/approvals.py)."""

from integrations.llm_client import call_llm

SYSTEM_PROMPT = """You are the Communication Agent inside Threshold. \
Draft a short, professional Slack message to an internal approver \
asking them to review an attached artifact. Calibrate tone to the \
urgency level given. Never sound robotic or repeat the exact same \
phrasing twice for the same approver. Output only the message text."""


def draft_nudge(deal: dict, department: str, urgency: str, root_cause: str) -> str:
    user_prompt = f"""
Deal: {deal['customer_name']}, ${deal['value']}.
Department: {department}.
Urgency: {urgency}.
Context / predicted friction: {root_cause}.

Draft the Slack nudge message.
"""
    return call_llm(SYSTEM_PROMPT, user_prompt, max_tokens=200)
