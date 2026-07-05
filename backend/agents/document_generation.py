"""Document Generation Agent — drafts the specific artifact tailored to
the approver's Behavioral Twin, not a generic template."""

from sqlalchemy.orm import Session
from behavioral_twins.twin_store import get_twin
from integrations.llm_client import call_llm

SYSTEM_PROMPT = """You are the Document Generation Agent inside \
Threshold. Draft the exact internal approval artifact requested, \
tailored to the specific format and structure that this approver has \
historically responded to fastest. Be concise, concrete, and use real \
deal numbers. Do not add commentary outside the document itself."""


def generate_artifact(db: Session, deal: dict, approver_id: str, department: str) -> str:
    twin = get_twin(db, approver_id)
    preferred_format = twin.fastest_responding_format if twin else "a standard summary"

    user_prompt = f"""
Draft a {department} approval artifact for this deal:
- Customer: {deal['customer_name']}
- Value: ${deal['value']}
- Discount: {deal.get('discount_percent', 0)}%
- Product type: {deal.get('product_type')}
- Customer segment: {deal.get('customer_segment')}

This approver responds fastest to: {preferred_format}.
Draft the artifact in that exact style.
"""
    return call_llm(SYSTEM_PROMPT, user_prompt, max_tokens=600)
