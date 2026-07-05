"""Delay Intelligence Agent — predicts bottleneck risk and explains why,
grounded in the approver's Behavioral Twin (not just generic deal
attributes). This is the core differentiator agent."""

import json

from sqlalchemy.orm import Session
from behavioral_twins.twin_store import get_twin
from integrations.llm_client import call_llm

SYSTEM_PROMPT = """You are the Delay Intelligence Agent inside Threshold, \
an internal deal-friction assistant. Given a deal and a specific \
approver's historical behavioral profile, predict the likelihood and \
expected length of delay, and explain the root cause in one sentence. \
Respond ONLY with JSON in this exact shape, no other text: \
{"delay_probability": 0-1 float, "expected_delay_days": float, \
"root_cause": "string", "confidence": 0-1 float}"""


def predict_delay(db: Session, deal: dict, approver_id: str) -> dict:
    twin = get_twin(db, approver_id)

    twin_context = (
        f"Approver avg turnaround: {twin.avg_turnaround_days} days. "
        f"Fastest-responding artifact format: {twin.fastest_responding_format}. "
        f"Known slow-down trigger: {twin.slowest_trigger}. "
        f"Deals reviewed historically: {twin.total_deals_reviewed}."
        if twin
        else "No historical profile yet for this approver."
    )

    user_prompt = f"""
Deal: value=${deal['value']}, product_type={deal.get('product_type')}, \
discount_percent={deal.get('discount_percent', 0)}, \
customer_segment={deal.get('customer_segment')}.

Approver behavioral profile: {twin_context}

Predict this approval's delay risk.
"""

    raw = call_llm(SYSTEM_PROMPT, user_prompt, max_tokens=300)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fallback so a live demo never crashes on a malformed LLM response
        return {
            "delay_probability": 0.5,
            "expected_delay_days": twin.avg_turnaround_days if twin else 3.0,
            "root_cause": "Unable to parse detailed reasoning; using historical average.",
            "confidence": 0.3,
        }
