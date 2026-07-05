import uuid
from datetime import datetime

from sqlalchemy import Column, String, Float, Integer, DateTime
from db.database import Base


class Deal(Base):
    __tablename__ = "deals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_name = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    discount_percent = Column(Float, default=0.0)
    product_type = Column(String, default="standard")
    customer_segment = Column(String, default="enterprise")
    stage = Column(String, default="verbal_agreement")
    momentum_score = Column(Integer, default=100)
    status = Column(String, default="active")  # active | stalled | closed
    created_at = Column(DateTime, default=datetime.utcnow)
