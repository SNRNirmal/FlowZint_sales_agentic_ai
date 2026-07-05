"""Long-term / cross-deal memory.

Deliberately minimal per the "do not over-engineer" instruction: this
is a single read query against the existing learning_log table, not a
new vector store or separate database. Its only job is to give the
Delay Intelligence node (Module 6) a fallback signal when a specific
approver has no behavioral twin yet (confidence 0.0) — instead of
guessing blind, it can reason from "how has this department/product
combination historically behaved across all approvers."

Extensible: a vector-store-backed semantic version of this same
function signature is a drop-in replacement later, without touching
any node code, since nodes only ever call
`get_department_pattern()`.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func

from models.learning_log import LearningLog
from models.approval import Approval


def get_department_pattern(db: Session, department: str) -> dict:
    """Returns the org-wide average approval duration for a department,
    computed from every past closed approval on record — a cross-deal
    pattern, not tied to any single approver's twin."""

    avg_duration = (
        db.query(func.avg(LearningLog.approval_duration_days))
        .join(Approval, Approval.deal_id == LearningLog.deal_id)
        .filter(Approval.department == department)
        .scalar()
    )

    sample_size = (
        db.query(func.count(LearningLog.id))
        .join(Approval, Approval.deal_id == LearningLog.deal_id)
        .filter(Approval.department == department)
        .scalar()
    )

    return {
        "department": department,
        "org_avg_turnaround_days": round(avg_duration, 2) if avg_duration else None,
        "sample_size": sample_size or 0,
    }
