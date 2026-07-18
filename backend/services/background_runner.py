"""Background pipeline runner for the Threshold LangGraph workflow.

The webhook route fires run_graph_background() as an asyncio.create_task()
and returns HTTP 202 immediately.  This module owns the long-running work:

  1. Opens its own DB session (the request session is already closed).
  2. Marks the DealJob as "running".
  3. Runs process_deal_via_graph() — the full 3-4 min LangGraph pipeline.
  4. Updates DealJob.progress at explicit checkpoints between node calls.
  5. Marks the job "completed" or "failed" when the graph exits.

Progress is updated at five explicit points bracketing the three LLM-heavy
nodes.  The previous monkey-patch approach corrupted the debug_logger
singleton under concurrent requests; explicit checkpoints are simpler,
safer, and correct across any number of concurrent pipelines.

Progress map:
  pending                  →   0
  graph started            →   5
  delay_intelligence done  →  40
  document_generator done  →  70
  communication_planner done→ 90
  graph END                → 100
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from db.database import SessionLocal
from models.deal import Deal
from models.deal_job import DealJob
from services.deal_service import process_deal_via_graph

logger = logging.getLogger("threshold.services.background_runner")


# ---------------------------------------------------------------------------
# Progress reporter
# ---------------------------------------------------------------------------

class ProgressReporter:
    """Write node progress to the DealJob row in an isolated transaction.

    Each report() call opens a fresh SessionLocal, writes, commits, and
    closes within a single synchronous call stack.  This means:
      a) The long-running graph session never blocks the polling reader.
      b) Multiple concurrent background tasks each hold their own reporter
         referencing their own deal_id — zero shared mutable state.
    """

    def __init__(self, deal_id: str) -> None:
        self.deal_id = deal_id

    def report(self, node: str, progress: int, status: Optional[str] = None) -> None:
        db = SessionLocal()
        try:
            job = db.query(DealJob).filter(DealJob.deal_id == self.deal_id).first()
            if job is None:
                logger.warning("ProgressReporter: DealJob not found for deal_id=%s", self.deal_id)
                return
            job.current_node = node
            job.progress = progress
            if status:
                job.pipeline_status = status
            db.commit()
        except Exception:
            logger.exception("ProgressReporter: failed to update job for deal_id=%s", self.deal_id)
            db.rollback()
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

async def run_graph_background(deal_id: str) -> None:
    """Execute the full Threshold pipeline for deal_id as an asyncio task.

    Called via asyncio.create_task() from the webhook route so the HTTP
    response is returned before any LLM inference begins.

    Each pipeline run has its own reporter, db session, and deal_id — fully
    isolated.  No global state is mutated; concurrent runs are safe.
    """
    reporter = ProgressReporter(deal_id)
    db = SessionLocal()

    try:
        # ------------------------------------------------------------------
        # Mark job as running
        # ------------------------------------------------------------------
        job = db.query(DealJob).filter(DealJob.deal_id == deal_id).first()
        if job is None:
            logger.error("run_graph_background: no DealJob row for deal_id=%s", deal_id)
            return

        job.pipeline_status = "running"
        job.started_at = datetime.utcnow()
        job.progress = 5
        job.current_node = "starting"
        db.commit()

        logger.info("[START] pipeline deal_id=%s", deal_id)

        # ------------------------------------------------------------------
        # Load the Deal ORM object
        # ------------------------------------------------------------------
        deal = db.query(Deal).filter(Deal.id == deal_id).first()
        if deal is None:
            raise ValueError(f"Deal {deal_id} not found in DB")

        # ------------------------------------------------------------------
        # Run the graph.
        # Progress is reported AFTER each phase completes because the graph
        # nodes are internal — we cannot inject callbacks without modifying
        # every node.  Reporting after-completion is conservative but correct:
        # the polling endpoint will show the last completed node.
        # ------------------------------------------------------------------
        logger.info("[START] full LangGraph pipeline deal_id=%s", deal_id)

        _STEP_PROGRESS = {
            "delay_intelligence": 40,
            "document_generator": 70,
            "communication_planner": 90,
        }

        def on_progress(node_name: str) -> None:
            if node_name in _STEP_PROGRESS:
                reporter.report(node_name, _STEP_PROGRESS[node_name])

        final_state = await process_deal_via_graph(db, deal, on_progress)

        reporter.report("end", 100, status="completed")
        logger.info("[END]   full LangGraph pipeline deal_id=%s", deal_id)

        # ------------------------------------------------------------------
        # Persist completion on the main session as well (belt-and-suspenders)
        # ------------------------------------------------------------------
        job = db.query(DealJob).filter(DealJob.deal_id == deal_id).first()
        if job:
            job.pipeline_status = "completed"
            job.progress = 100
            job.current_node = "end"
            job.finished_at = datetime.utcnow()
            db.commit()

        logger.info("Pipeline completed successfully deal_id=%s", deal_id)

    except Exception as exc:
        logger.exception("Background job failed: %s", exc)
        try:
            # Best-effort failure mark in a fresh session — the main one may
            # be in a broken transaction state after an exception.
            err_db = SessionLocal()
            try:
                job = err_db.query(DealJob).filter(DealJob.deal_id == deal_id).first()
                if job:
                    job.pipeline_status = "failed"
                    job.error = str(exc)
                    job.finished_at = datetime.utcnow()
                    err_db.commit()
            finally:
                err_db.close()
        except Exception:
            logger.exception("Failed to write error status for deal_id=%s", deal_id)
    finally:
        db.close()
