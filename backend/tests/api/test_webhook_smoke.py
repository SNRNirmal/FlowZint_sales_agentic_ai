"""End-to-end HTTP smoke: POST /webhooks/crm completes a full pipeline run.

Regression for Bug 3 (Task 6.5 review): ainvoke's dict return crashed
deal_service with AttributeError -> HTTP 500. This is the first test that
drives the actual FastAPI app through its real lifespan.
"""

from fastapi.testclient import TestClient

import main
from db.database import get_db


def test_crm_webhook_completes_full_pipeline_run(db_session):
    # The app's import-time engine defaults to SingletonThreadPool under the
    # suite-forced in-memory DATABASE_URL, handing asyncio.to_thread workers
    # fresh EMPTY-database connections (the exact hazard conftest's db_engine
    # fixture documents and solves with StaticPool). Point the route at the
    # StaticPool test session via FastAPI's standard override seam;
    # production uses a file-backed SQLite DB and has no such failure mode.
    def _test_db():
        yield db_session

    main.app.dependency_overrides[get_db] = _test_db
    try:
        with TestClient(main.app) as client:
            resp = client.post(
                "/webhooks/crm",
                json={
                    "customer_name": "Acme Corp",
                    "value": 180_000,
                    "discount_percent": 20,
                    "product_type": "custom",
                    "customer_segment": "enterprise",
                },
            )
    finally:
        main.app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["deal_id"]
    assert len(body["drafted_actions"]) == 5
    for action in body["drafted_actions"]:
        assert action["artifact_draft"]
        assert action["nudge_draft"]
        assert action["review_status"] == "awaiting_human_review"
