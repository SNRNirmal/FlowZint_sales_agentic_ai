import uuid

from sqlalchemy import Column, String, Float, ForeignKey
from db.database import Base


class LearningLog(Base):
    __tablename__ = "learning_log"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_id = Column(String, ForeignKey("deals.id"), nullable=False)
    approver_id = Column(String, ForeignKey("behavioral_twins.approver_id"), nullable=False)
    delay_reason = Column(String, nullable=True)
    successful_action = Column(String, nullable=True)
    approval_duration_days = Column(Float, nullable=True)
