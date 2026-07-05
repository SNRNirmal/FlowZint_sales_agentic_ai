from datetime import datetime

from sqlalchemy.orm import Session
from models.behavioral_twin import BehavioralTwin


def get_twin(db: Session, approver_id: str) -> BehavioralTwin | None:
    return db.query(BehavioralTwin).filter(BehavioralTwin.approver_id == approver_id).first()


def upsert_twin(db: Session, approver_id: str, **fields) -> BehavioralTwin:
    twin = get_twin(db, approver_id)
    if not twin:
        twin = BehavioralTwin(approver_id=approver_id, **fields)
        db.add(twin)
    else:
        for key, value in fields.items():
            setattr(twin, key, value)
        twin.last_updated = datetime.utcnow()
    db.commit()
    db.refresh(twin)
    return twin


def update_twin_after_deal(
    db: Session,
    approver_id: str,
    actual_delay_days: float,
    artifact_format_used: str,
    weight_recent: float = 0.4,
) -> BehavioralTwin:
    """Learning Agent update rule: weighted rolling average, recent deals
    weighted higher. Promotes the fastest-performing format as the new
    default for this approver."""
    twin = get_twin(db, approver_id)
    if not twin:
        return upsert_twin(
            db,
            approver_id,
            avg_turnaround_days=actual_delay_days,
            fastest_responding_format=artifact_format_used,
            total_deals_reviewed=1,
        )

    new_avg = (twin.avg_turnaround_days * (1 - weight_recent)) + (actual_delay_days * weight_recent)

    # If this deal's format resolved faster than the historical average,
    # promote it as the new fastest-responding format.
    fastest_format = twin.fastest_responding_format
    if actual_delay_days < twin.avg_turnaround_days:
        fastest_format = artifact_format_used

    return upsert_twin(
        db,
        approver_id,
        avg_turnaround_days=round(new_avg, 2),
        fastest_responding_format=fastest_format,
        total_deals_reviewed=twin.total_deals_reviewed + 1,
    )
