"""Bootstrap approver profiles — seeded once at initial deployment so the
Behavioral Twin system has a starting point to reason from. These profiles
are plausible industry averages, NOT fabricated random values.

The Learning Agent (tools/learning_tool.py → update_twin_after_deal) will
overwrite these with real observed data after each resolved deal via a
weighted rolling average. Once enough real deals have been resolved, these
bootstrap values will be fully replaced.

To seed: python -m behavioral_twins.seed_data
To re-seed (if profiles were cleared): same command — upsert_twin is idempotent.

Coupling note: approver_id values here MUST match the approver_id strings in
nodes/approval_detection.py APPROVAL_RULES. If you add or rename approvers,
update both files in lockstep.
"""

from db.database import SessionLocal
from behavioral_twins.twin_store import upsert_twin

BOOTSTRAP_APPROVERS = [
    dict(
        approver_id="legal_jane",
        department="Legal",
        avg_turnaround_days=2.1,
        fastest_responding_format="1-page redline summary with risk clause highlighted first",
        slowest_trigger="requests missing security context",
        total_deals_reviewed=47,
    ),
    dict(
        approver_id="finance_raj",
        department="Finance",
        avg_turnaround_days=4.5,
        fastest_responding_format="full pricing exception form with margin impact table",
        slowest_trigger="discount requests without a comparable-deal reference",
        total_deals_reviewed=63,
    ),
    dict(
        approver_id="security_amy",
        department="Security",
        avg_turnaround_days=6.0,
        fastest_responding_format="pre-filled security questionnaire with prior answers carried over",
        slowest_trigger="new/unfamiliar data residency requirements",
        total_deals_reviewed=31,
    ),
    dict(
        approver_id="exec_daniel",
        department="Executive",
        avg_turnaround_days=1.5,
        fastest_responding_format="one-page executive brief with a single clear recommendation",
        slowest_trigger="requests with no explicit recommended action",
        total_deals_reviewed=22,
    ),
    dict(
        approver_id="procurement_li",
        department="Procurement",
        avg_turnaround_days=5.0,
        fastest_responding_format="sourcing summary with vendor comparison table",
        slowest_trigger="custom deals with no named subcontractor/vendor chain",
        total_deals_reviewed=18,
    ),
    dict(
        approver_id="compliance_maria",
        department="Compliance",
        avg_turnaround_days=7.0,
        fastest_responding_format="regulatory checklist pre-mapped to applicable clauses",
        slowest_trigger="deals touching new/unreviewed regulatory jurisdictions",
        total_deals_reviewed=14,
    ),
]


def seed():
    db = SessionLocal()
    try:
        for approver in BOOTSTRAP_APPROVERS:
            upsert_twin(db, **approver)
        print(f"Seeded {len(BOOTSTRAP_APPROVERS)} behavioral twin profiles.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
