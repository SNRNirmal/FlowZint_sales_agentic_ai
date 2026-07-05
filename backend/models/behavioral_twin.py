from datetime import datetime

from sqlalchemy import Column, String, Float, Integer, DateTime
from db.database import Base


class BehavioralTwin(Base):
    """The core differentiator: a live profile per internal approver,
    updated by the Learning Agent after every closed deal."""

    __tablename__ = "behavioral_twins"

    approver_id = Column(String, primary_key=True)
    department = Column(String, nullable=False)
    avg_turnaround_days = Column(Float, default=3.0)
    fastest_responding_format = Column(String, default="standard summary")
    slowest_trigger = Column(String, default="incomplete context")
    total_deals_reviewed = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)
