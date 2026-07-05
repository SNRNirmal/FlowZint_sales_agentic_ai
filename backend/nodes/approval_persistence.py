"""Approval Persistence Node — writes detected approvals to the database
and computes the initial Deal Momentum Score.

Architecture position:
  GraphState.approvals (from approval_detection_node)
      →  this node  →  approvals table (via database_tool.persist_approvals)
                    →  GraphState.momentum_score (initial score, post-persist)
                    →  deals table (Deal.momentum_score, via compute_momentum_score)

Why this node exists
--------------------
nodes/approval_detection.py is a pure-reasoning node: it creates
ApprovalStatus objects in memory and populates GraphState.approvals. It
deliberately makes no database writes — side effects inside a reasoning
node violate the architecture's separation of concerns.

This node is the execution step that bridges the reasoning output to the
database. Without it, the downstream approval routes
(POST /approvals/{id}/send, /hold, /resolve) all return HTTP 404 because
the rows they query do not exist.

Why momentum is computed here
------------------------------
GraphState.momentum_score is the single source of truth for momentum
during a graph run. It must reflect reality. After approvals are
persisted, the correct initial score can be computed from those rows
(each pending approval deducts points). Computing it here — in the
same node, with the same DB session, immediately after the persist —
avoids:
  - A duplicate DB session or separate compute node
  - Stale momentum in GraphState (which was otherwise always 100)
  - Multiple calls to compute_momentum_score for the same deal
  - Any discrepancy between GraphState and the DB row

The result is written to both GraphState.momentum_score (via the
node's return dict) and to Deal.momentum_score in the DB (as a side
effect of compute_momentum_score). From this point forward both are
in sync.

Design notes
------------
- Calls tools.database_tool.persist_approvals via its .coroutine()
  interface, passing the injected DB session directly. This bypasses
  LangChain's InjectedToolArg resolution (which only applies during
  ainvoke()) and passes the session from config["configurable"]["db"]
  exactly as every other tool-calling node does (see
  behavioral_twin_retrieval.py for the established pattern).
- persist_approvals is idempotent: rows whose approval_id already exists
  in the database are skipped, not duplicated. Safe to re-run on retry.
- compute_momentum_score is called after persist so the pending rows are
  visible to the query; it writes the score to Deal.momentum_score and
  returns the int that this node puts into GraphState.momentum_score.
- Momentum computation failure is non-fatal: the node logs the error,
  leaves GraphState.momentum_score at its current value (the DB value
  written by the persist step is the fallback), and continues the graph.
- Node-level error handling: if the DB write fails after retries (the
  retry loop lives inside tools/database_tool._persist_approvals_in_db),
  the exception is caught here, logged, and an error audit entry is
  written. The node does not raise — a DB persistence failure should not
  prevent the graph from continuing to draft artifacts and nudges, which
  can still be returned to the caller and reviewed by the operator before
  anything is sent externally.
"""

from __future__ import annotations

import asyncio
import logging

from langchain_core.runnables import RunnableConfig

from nodes._node_utils import get_db_session
from schemas.graph_state import GraphState
from tools.database_tool import persist_approvals
from tools.momentum_tool import compute_momentum_score

logger = logging.getLogger("threshold.nodes.approval_persistence")


async def approval_persistence_node(state: GraphState, config: RunnableConfig | None = None) -> dict:
    """LangGraph execution node: Approval Persistence.

    Writes the ApprovalStatus records produced by approval_detection_node
    into the ``approvals`` database table, then computes the initial
    Deal Momentum Score and writes it to both ``GraphState.momentum_score``
    and the ``deals`` table.

    Parameters
    ----------
    state : GraphState
        Must have ``state.approvals`` populated by the preceding
        approval_detection_node.
    config : RunnableConfig, optional
        Expected to carry a DB session at ``config["configurable"]["db"]``.
        Falls back to a locally-opened session for isolated unit testing.

    Returns
    -------
    dict
        Partial state update containing:
        - ``momentum_score``: initial deal momentum score (post-persist)
        - ``audit_log``: one entry recording success or failure
        - ``current_node``: ``"approval_persistence"``
    """
    deal = state.deal
    approvals = state.approvals

    if not approvals:
        # Defensive guard: the conditional edge before this node routes to
        # END when there are no approvals, so this branch should never
        # fire in production. Logged as a warning so it is visible if the
        # routing logic ever changes.
        logger.warning(
            "approval_persistence_node called with no approvals — nothing to persist",
            extra={"deal_id": deal.deal_id},
        )
        return {
            "current_node": "approval_persistence",
            "audit_log": [
                {
                    "event": "approval_persistence_skipped",
                    "deal_id": deal.deal_id,
                    "reason": "no approvals in state",
                    "node": "approval_persistence",
                }
            ],
        }

    db, owns_session = get_db_session(config)

    try:
        # ------------------------------------------------------------------
        # Step 1: Persist approval rows to the database
        # ------------------------------------------------------------------
        logger.info(
            "Persisting detected approvals to database",
            extra={"deal_id": deal.deal_id, "count": len(approvals)},
        )

        # Call via .coroutine() so the db session is passed directly,
        # bypassing InjectedToolArg resolution which only applies to ainvoke().
        result = await persist_approvals.coroutine(
            deal_id=deal.deal_id,
            approvals=approvals,
            db=db,
        )

        if result.success:
            logger.info(
                "Approvals persisted successfully",
                extra={
                    "deal_id": deal.deal_id,
                    "persisted": result.persisted_count,
                    "skipped_existing": result.skipped_existing_count,
                },
            )
            audit_entry = {
                "event": "approval_persistence_complete",
                "deal_id": deal.deal_id,
                "persisted_count": result.persisted_count,
                "skipped_existing_count": result.skipped_existing_count,
                "node": "approval_persistence",
            }
        else:
            logger.error(
                "Approval persistence tool reported failure",
                extra={"deal_id": deal.deal_id, "error": result.error},
            )
            audit_entry = {
                "event": "approval_persistence_tool_failure",
                "deal_id": deal.deal_id,
                "error": result.error,
                "node": "approval_persistence",
            }
            return {
                "current_node": "approval_persistence",
                "audit_log": [audit_entry],
            }

        # ------------------------------------------------------------------
        # Step 2: Compute initial momentum score
        #
        # compute_momentum_score reads the now-persisted approval rows,
        # applies WEIGHTS, clamps to [0, 100], writes the result to
        # Deal.momentum_score in the DB, and returns the int.
        #
        # Running in a thread because compute_momentum_score is synchronous
        # SQLAlchemy — same pattern as every other sync DB call in the
        # async node layer.
        # ------------------------------------------------------------------
        try:
            momentum_score = await asyncio.to_thread(
                compute_momentum_score, db, deal.deal_id
            )
            logger.info(
                "Initial momentum score computed",
                extra={"deal_id": deal.deal_id, "momentum_score": momentum_score},
            )
            audit_entry["momentum_score"] = momentum_score
        except Exception as momentum_exc:
            # Momentum failure is non-fatal: the graph continues without
            # an updated score in GraphState. The DB row retains whatever
            # value it had (the Deal was just created, so momentum_score
            # defaults to 100 from the ORM model). Logged as ERROR so it
            # is visible in monitoring.
            logger.error(
                "Momentum score computation failed — GraphState.momentum_score "
                "will retain its current value",
                extra={"deal_id": deal.deal_id, "error": str(momentum_exc)},
                exc_info=True,
            )
            momentum_score = state.momentum_score  # preserve existing value

        return {
            "momentum_score": momentum_score,
            "current_node": "approval_persistence",
            "audit_log": [audit_entry],
        }

    except Exception as exc:
        logger.error(
            "approval_persistence_node raised an unhandled exception",
            extra={"deal_id": deal.deal_id, "error": str(exc)},
            exc_info=True,
        )
        return {
            "current_node": "approval_persistence",
            "audit_log": [
                {
                    "event": "approval_persistence_error",
                    "deal_id": deal.deal_id,
                    "error": str(exc),
                    "node": "approval_persistence",
                }
            ],
        }

    finally:
        if owns_session:
            db.close()
