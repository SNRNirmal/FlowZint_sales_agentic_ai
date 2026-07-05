"""Approval Detection Agent — rule-based for hackathon speed.
Determines which internal approvals a deal requires based on its
attributes, and which specific approver owns each one."""

from typing import List, Dict


def detect_required_approvals(deal: dict) -> List[Dict]:
    required = []

    if deal["value"] >= 50000 or deal.get("discount_percent", 0) >= 15:
        required.append({"department": "Finance", "approver_id": "finance_raj"})

    if deal.get("product_type") == "custom" or deal["value"] >= 100000:
        required.append({"department": "Legal", "approver_id": "legal_jane"})

    if deal.get("customer_segment") == "enterprise":
        required.append({"department": "Security", "approver_id": "security_amy"})

    if deal["value"] >= 250000:
        required.append({"department": "Executive", "approver_id": "exec_daniel"})

    return required
