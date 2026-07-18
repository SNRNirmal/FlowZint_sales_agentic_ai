"""CRM webhook route — entry point for the LangGraph pipeline.

POST /webhooks/crm receives a CRM stage-change payload, persists the deal,
creates a DealJob tracking row, fires the pipeline as an asyncio background
task, and returns HTTP 202 Accepted immediately.

The HTTP connection is held open for less than 100 ms regardless of how long
the pipeline takes.  Callers poll GET /deals/{deal_id}/status for progress.

Why asyncio.create_task() rather than FastAPI BackgroundTasks?
  - FastAPI BackgroundTasks run after the response is sent but inside the
    same request context, which means the request DB session is still
    technically "in scope" while the background runs.  For a pipeline that
    takes 3-4 min this causes SQLAlchemy session lifecycle issues.
  - asyncio.create_task() schedules the coroutine on the event loop
    independently of the HTTP request context.  The background runner opens
    its own SessionLocal and manages its own transaction lifecycle.
"""

import asyncio
import uuid
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db
from models.deal import Deal
from models.deal_job import DealJob
from services.background_runner import run_graph_background

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger("threshold.routes.webhooks")


class CRMWebhookPayload(BaseModel):
    customer_name: str
    value: float = Field(gt=0)
    discount_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    product_type: str = Field(default="standard")
    customer_segment: str = Field(default="enterprise")
    stage: str = Field(default="verbal_agreement")


@router.post("/crm", status_code=202)
async def crm_webhook(payload: CRMWebhookPayload, db: Session = Depends(get_db)):
    """CRM stage-change webhook — creates a deal and starts background processing.

    Returns HTTP 202 Accepted immediately.  The full LangGraph pipeline
    (delay_intelligence → document_generator → communication_planner → …)
    runs asynchronously.  Poll GET /deals/{deal_id}/status for progress.
    """
    from debug_logger import dl
    dl.start_request()
    dl.log_step(1, "Received payload.", node="webhook_route", input_keys=list(payload.model_dump().keys()))

    # ------------------------------------------------------------------
    # 1. Parse payload and construct Deal ORM object
    # ------------------------------------------------------------------
    deal = Deal(
        id=str(uuid.uuid4()),
        customer_name=payload.customer_name,
        value=payload.value,
        discount_percent=payload.discount_percent,
        product_type=payload.product_type,
        customer_segment=payload.customer_segment,
        stage=payload.stage,
    )
    dl.log_step(2, "Parsed payload successfully.", node="webhook_route")

    # ------------------------------------------------------------------
    # 2. Persist the Deal row
    # ------------------------------------------------------------------
    try:
        db.add(deal)
        db.commit()
        db.refresh(deal)
        dl.log_step(3, "Created Deal object.", node="webhook_route", output_keys=["deal_id"])
    except Exception as exc:
        dl.log_step(3, "Failed to create Deal object.", node="webhook_route", exc=str(exc))
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"detail": f"Failed to persist deal: {exc}"},
        )

    # ------------------------------------------------------------------
    # 3. Create a DealJob tracking row in "pending" state.
    #    The background runner will advance it through running → completed.
    # ------------------------------------------------------------------
    try:
        job = DealJob(
            deal_id=deal.id,
            pipeline_status="pending",
            progress=0,
        )
        db.add(job)
        db.commit()
        dl.log_step(4, "Created DealJob tracking row.", node="webhook_route")
    except Exception as exc:
        dl.log_step(4, "Failed to create DealJob row.", node="webhook_route", exc=str(exc))
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"detail": f"Failed to create job tracker: {exc}"},
        )

    # ------------------------------------------------------------------
    # 4. Fire the pipeline as an asyncio background task and return 202.
    #    The task runs on the same event loop; it opens its own DB session.
    # ------------------------------------------------------------------
    asyncio.create_task(
        run_graph_background(deal.id),
        name=f"pipeline-{deal.id}",
    )

    logger.info(
        "Pipeline dispatched as background task",
        extra={"deal_id": deal.id, "customer_name": deal.customer_name},
    )
    dl.log_step(5, "Pipeline dispatched — returning 202.", node="webhook_route")
    dl.end_request()

    return JSONResponse(
        status_code=202,
        content={
            "deal_id": deal.id,
            "status": "processing",
            "message": "Deal processing started. Poll GET /deals/{deal_id}/status for progress.",
        },
    )
