"""HTTP contract tests for /deals and /webhooks/crm. The graph is
patched at the service seam — routes are tested as HTTP adapters."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from db.database import get_db
from main import app
from models.approval import Approval
from models.deal import Deal
from schemas.graph_state import ApprovalStatus, RiskScore, new_graph_state
from tests.conftest import make_deal


@pytest.fixture()
def client(db_engine):
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # NOTE: no `with` — lifespan (init_db on the real file DB + graph
    # pre-warm) must NOT run in route tests.
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_deal(db_session, deal_id="deal-api-1") -> Deal:
    deal = Deal(id=deal_id, customer_name="Acme Corp", value=180_000)
    db_session.add(deal)
    db_session.commit()
    return deal


def test_list_deals_returns_seeded_rows(client, db_session):
    _seed_deal(db_session, "deal-a")
    _seed_deal(db_session, "deal-b")

    resp = client.get("/deals/")

    assert resp.status_code == 200
    assert {d["id"] for d in resp.json()} == {"deal-a", "deal-b"}


def test_get_deal_returns_deal_with_its_approvals(client, db_session):
    _seed_deal(db_session, "deal-a")
    db_session.add(
        Approval(id="ap-1", deal_id="deal-a", department="Finance", approver_id="finance_raj")
    )
    db_session.commit()

    resp = client.get("/deals/deal-a")

    assert resp.status_code == 200
    body = resp.json()
    assert body["deal"]["id"] == "deal-a"
    assert body["approvals"][0]["id"] == "ap-1"


def test_get_missing_deal_is_404(client):
    assert client.get("/deals/nope").status_code == 404


def test_crm_webhook_persists_deal_and_maps_drafted_actions(client, db_session, monkeypatch):
    async def fake_process(db, deal):
        state = new_graph_state(make_deal(deal_id=deal.id))
        state.approvals = [
            ApprovalStatus(approval_id="ap-9", department="Finance", approver_id="finance_raj")
        ]
        state.risk_scores = {
            "finance_raj": RiskScore(
                approver_id="finance_raj",
                delay_probability=0.42,
                expected_delay_days=3.5,
                root_cause="test",
                confidence=0.8,
            )
        }
        state.artifacts = {"finance_raj": "artifact text"}
        state.nudges = {"finance_raj": "nudge text"}
        return state

    monkeypatch.setattr("routes.webhooks.process_deal_via_graph", fake_process)

    resp = client.post("/webhooks/crm", json={"customer_name": "Acme Corp", "value": 180000})

    assert resp.status_code == 200
    body = resp.json()
    assert db_session.query(Deal).filter_by(id=body["deal_id"]).count() == 1
    assert "momentum_score" in body
    action = body["drafted_actions"][0]
    assert action["approval_id"] == "ap-9"
    assert action["artifact_draft"] == "artifact text"
    assert action["nudge_draft"] == "nudge text"
    assert action["review_status"] == "awaiting_human_review"
    assert action["prediction"]["delay_probability"] == 0.42
