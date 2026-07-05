"""Run once at startup (or via a one-off script) to seed demo approver
profiles so the Delay Intelligence Agent has something real to reason
over during the live demo."""

from db.database import SessionLocal
from behavioral_twins.twin_store import upsert_twin

DEMO_APPROVERS = [
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
        for approver in DEMO_APPROVERS:
            upsert_twin(db, **approver)
        print(f"Seeded {len(DEMO_APPROVERS)} behavioral twin profiles.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
