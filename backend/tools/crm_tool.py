"""CRM Tool — execution bridge to the CRM data layer.

This tool performs two atomic CRM operations:
  1. Fetch a deal by ID → typed DealInfo snapshot.
  2. Update a deal's stage → typed confirmation with before/after.

It NEVER decides which stage a deal should move to. Reasoning nodes
make that decision and pass the target stage as an input argument.

Architecture position:
  Reasoning Node  →  crm_tool  →  models/deal.py (SQLAlchemy ORM)
       decides         executes        system of record

Design notes:
  - Async execution via asyncio.to_thread() — keeps compatibility with
    the existing synchronous SQLAlchemy layer (Modules 1 & 2) while
    preventing event-loop blocking in LangGraph parallel branches.
  - InjectedToolArg hides the DB session from the LLM tool schema.
  - Pydantic v2 result types wrap every return so tools never leak raw
    dicts or strings into the graph state.
  - tenacity retry handles transient DB failures (lock contention,
    connection drops) with exponential backoff.
  - All operations are logged with structured context for observability.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from langchain_core.tools import tool, InjectedToolArg
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from models.deal import Deal
from schemas.graph_state import DealInfo

logger = logging.getLogger("threshold.tools.crm")

# -----------------------------------------------------------------------
# Valid stage transitions — kept here as a constant so the tool can
# validate that the caller (reasoning node) isn't requesting an invalid
# transition. This is NOT business logic; it's input validation, the same
# way a REST endpoint validates enum values before writing to the DB.
# -----------------------------------------------------------------------

VALID_STAGES: set[str] = {
    "verbal_agreement",
    "approvals_in_progress",
    "approved",
    "closed_won",
    "closed_lost",
    "stalled",
}


# -----------------------------------------------------------------------
# Pydantic v2 Input / Output Schemas
# -----------------------------------------------------------------------

class CrmFetchInput(BaseModel):
    """Input schema for crm_fetch_deal."""

    deal_id: str = Field(
        ...,
        description="The unique identifier of the deal to fetch from the CRM.",
    )


class CrmFetchResult(BaseModel):
    """Typed result from a CRM deal fetch operation."""

    success: bool
    deal: DealInfo | None = None
    error: str | None = None


class CrmUpdateStageInput(BaseModel):
    """Input schema for crm_update_deal_stage."""

    deal_id: str = Field(
        ...,
        description="The unique identifier of the deal whose stage should be updated.",
    )
    new_stage: str = Field(
        ...,
        description=(
            "The target stage to transition the deal to. "
            "Must be one of: verbal_agreement, approvals_in_progress, "
            "approved, closed_won, closed_lost, stalled."
        ),
    )


class CrmUpdateResult(BaseModel):
    """Typed result from a CRM deal stage update operation."""

    success: bool
    deal: DealInfo | None = None
    previous_stage: str | None = None
    new_stage: str | None = None
    error: str | None = None


# -----------------------------------------------------------------------
# Internal helpers (retry-wrapped DB operations)
#
# These remain synchronous because the DB layer (Module 1) uses sync
# SQLAlchemy. The async tool functions call them via asyncio.to_thread()
# to avoid blocking the event loop.
# -----------------------------------------------------------------------

def _derive_status(stage: str) -> str:
    """Derive the Deal.status column value from a stage transition.

    This is referential integrity — the status column must stay
    consistent with the stage column. The Deal model has both:
      - stage: verbal_agreement | approvals_in_progress | approved | ...
      - status: active | stalled | closed

    Mapping rules:
      closed_won / closed_lost → "closed"
      stalled                  → "stalled"
      everything else          → "active"
    """
    if stage in {"closed_won", "closed_lost"}:
        return "closed"
    if stage == "stalled":
        return "stalled"
    return "active"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _fetch_deal_from_db(db: Session, deal_id: str) -> Deal | None:
    """Fetch a Deal row by primary key. Wrapped in retry for resilience
    against transient SQLite/Postgres lock contention or connection
    drops in production."""
    return db.query(Deal).filter(Deal.id == deal_id).first()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _update_deal_stage_in_db(db: Session, deal: Deal, new_stage: str) -> None:
    """Persist a stage change and keep the status column in sync.
    Retry-wrapped for resilience against transient DB failures."""
    deal.stage = new_stage
    deal.status = _derive_status(new_stage)
    db.commit()
    db.refresh(deal)


def _deal_to_info(deal: Deal) -> DealInfo:
    """Convert a SQLAlchemy Deal row to the Pydantic DealInfo that the
    graph state expects. This is a pure mapping — no business logic."""
    return DealInfo(
        deal_id=deal.id,
        customer_name=deal.customer_name,
        value=deal.value,
        discount_percent=deal.discount_percent,
        product_type=deal.product_type,
        customer_segment=deal.customer_segment,
        stage=deal.stage,
    )


# -----------------------------------------------------------------------
# LangChain Tools (async)
#
# Both tools are async so LangGraph can invoke them concurrently in
# parallel branches (e.g., fetching deals for multiple approvers).
# DB calls are dispatched to a thread via asyncio.to_thread() to
# preserve compatibility with the existing synchronous SQLAlchemy layer.
# -----------------------------------------------------------------------

@tool(args_schema=CrmFetchInput)
async def crm_fetch_deal(
    deal_id: str,
    db: Annotated[Session, InjectedToolArg],
) -> CrmFetchResult:
    """Fetch a deal from the CRM by its unique ID.

    Returns a typed CrmFetchResult containing the deal data as a
    DealInfo snapshot, or an error message if the deal is not found.
    """
    logger.info("crm_fetch_deal called", extra={"deal_id": deal_id})

    try:
        deal = await asyncio.to_thread(_fetch_deal_from_db, db, deal_id)

        if deal is None:
            logger.warning(
                "Deal not found in CRM",
                extra={"deal_id": deal_id},
            )
            return CrmFetchResult(
                success=False,
                error=f"Deal '{deal_id}' not found in CRM.",
            )

        deal_info = _deal_to_info(deal)
        logger.info(
            "Deal fetched successfully",
            extra={"deal_id": deal_id, "stage": deal_info.stage},
        )
        return CrmFetchResult(success=True, deal=deal_info)

    except Exception as exc:
        logger.error(
            "CRM fetch failed after retries",
            extra={"deal_id": deal_id, "error": str(exc)},
            exc_info=True,
        )
        return CrmFetchResult(
            success=False,
            error=f"CRM fetch failed: {exc}",
        )


@tool(args_schema=CrmUpdateStageInput)
async def crm_update_deal_stage(
    deal_id: str,
    new_stage: str,
    db: Annotated[Session, InjectedToolArg],
) -> CrmUpdateResult:
    """Update a deal's stage in the CRM.

    The reasoning node decides the target stage; this tool only
    executes the persistence. Returns a typed CrmUpdateResult with
    the previous and new stage values.
    """
    logger.info(
        "crm_update_deal_stage called",
        extra={"deal_id": deal_id, "new_stage": new_stage},
    )

    # --- Input validation (not business logic, just enum enforcement) ---
    if new_stage not in VALID_STAGES:
        logger.warning(
            "Invalid stage requested",
            extra={"deal_id": deal_id, "new_stage": new_stage},
        )
        return CrmUpdateResult(
            success=False,
            error=f"Invalid stage '{new_stage}'. Valid stages: {sorted(VALID_STAGES)}",
        )

    try:
        deal = await asyncio.to_thread(_fetch_deal_from_db, db, deal_id)

        if deal is None:
            logger.warning(
                "Deal not found for stage update",
                extra={"deal_id": deal_id},
            )
            return CrmUpdateResult(
                success=False,
                error=f"Deal '{deal_id}' not found in CRM.",
            )

        previous_stage = deal.stage

        # --- Idempotency guard ---
        # If the deal is already at the requested stage, return success
        # without a DB write. Prevents wasteful commits and misleading
        # audit entries when a reasoning node retries or re-evaluates.
        if previous_stage == new_stage:
            logger.info(
                "Deal already at requested stage — no-op",
                extra={"deal_id": deal_id, "stage": new_stage},
            )
            deal_info = _deal_to_info(deal)
            return CrmUpdateResult(
                success=True,
                deal=deal_info,
                previous_stage=previous_stage,
                new_stage=new_stage,
            )

        await asyncio.to_thread(_update_deal_stage_in_db, db, deal, new_stage)

        deal_info = _deal_to_info(deal)
        logger.info(
            "Deal stage updated successfully",
            extra={
                "deal_id": deal_id,
                "previous_stage": previous_stage,
                "new_stage": new_stage,
                "derived_status": deal.status,
            },
        )
        return CrmUpdateResult(
            success=True,
            deal=deal_info,
            previous_stage=previous_stage,
            new_stage=new_stage,
        )

    except Exception as exc:
        logger.error(
            "CRM stage update failed after retries",
            extra={"deal_id": deal_id, "error": str(exc)},
            exc_info=True,
        )
        return CrmUpdateResult(
            success=False,
            error=f"CRM stage update failed: {exc}",
        )
