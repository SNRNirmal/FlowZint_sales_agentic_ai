import uuid

from sqlalchemy import Column, String, Float, ForeignKey
from db.database import Base


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_id = Column(String, ForeignKey("deals.id"), nullable=False)
    department = Column(String, nullable=False)  # Legal | Finance | Security | Executive
    approver_id = Column(String, ForeignKey("behavioral_twins.approver_id"), nullable=False)
    status = Column(String, default="pending")  # pending | sent | approved | rejected
    predicted_delay_days = Column(Float, nullable=True)
    actual_delay_days = Column(Float, nullable=True)
    artifact_format_used = Column(String, nullable=True)
