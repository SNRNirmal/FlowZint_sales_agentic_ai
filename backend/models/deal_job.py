"""DealJob — tracks the background LangGraph pipeline execution for a deal.

Separate from the Deal model deliberately: Deal.status tracks business state
(active / stalled / closed); DealJob.pipeline_status tracks infrastructure
state (pending / running / completed / failed).  Mixing them would couple
business logic to pipeline mechanics.

One DealJob is created per webhook invocation.  The background runner
updates it as each graph node completes so the polling endpoint can report
live progress without waiting for the full graph to finish.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey

from db.database import Base


class DealJob(Base):
    __tablename__ = "deal_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Business key — one job per deal invocation
    deal_id = Column(String, ForeignKey("deals.id"), nullable=False, index=True)

    # Pipeline lifecycle:  pending → running → completed | failed
    pipeline_status = Column(String, nullable=False, default="pending")

    # Name of the graph node currently executing (or last completed)
    current_node = Column(String, nullable=True)

    # 0–100 progress percentage, updated by the background runner at each
    # node boundary so callers can render a live progress bar
    progress = Column(Integer, nullable=False, default=0)

    # Populated only when pipeline_status == "failed"
    error = Column(Text, nullable=True)

    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
