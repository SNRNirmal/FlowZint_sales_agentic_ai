"""HTTP contract tests for the three human-review checkpoint endpoints.
resume_deal_graph, send_slack_message, and the learning/momentum tools
are patched IN THE ROUTE MODULE'S NAMESPACE (routes.approvals imports
them by name)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from db.database import get_db
from main import app
from models.approval import Approval
from models.deal import Deal


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
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded_approval(db_session):
    db_session.add(Deal(id="deal-1", customer_name="Acme Corp", value=180_000))
    db_session.add(
        Approval(id="ap-1", deal_id="deal-1", department="Finance", approver_id="finance_raj")
    )
    db_session.commit()
    return "ap-1"


@pytest.fixture()
def resume_recorder(monkeypatch):
    calls = {}

    async def fake_resume(deal_id, action, feedback="", reviewer="system"):
        calls.update(deal_id=deal_id, action=action)
        return None

    monkeypatch.setattr("routes.approvals.resume_deal_graph", fake_resume)
    return calls


@pytest.fixture()
def slack_recorder(monkeypatch):
    calls = {}

    def fake_slack(channel, text):
        calls.update(channel=channel, text=text)

    monkeypatch.setattr("routes.approvals.send_slack_message", fake_slack)
    return calls


def test_send_marks_sent_and_resumes_with_approve(
    client, db_session, seeded_approval, resume_recorder, slack_recorder
):
    resp = client.post(f"/approvals/{seeded_approval}/send", params={"nudge_text": "Please review"})

    assert resp.status_code == 200
    assert resp.json() == {"status": "sent", "approval_id": "ap-1"}
    db_session.expire_all()
    assert db_session.get(Approval, "ap-1").status == "sent"
    assert slack_recorder == {"channel": "#finance-approvals", "text": "Please review"}
    assert resume_recorder == {"deal_id": "deal-1", "action": "approve"}


def test_send_missing_approval_is_404(client, resume_recorder, slack_recorder):
    resp = client.post("/approvals/nope/send", params={"nudge_text": "x"})
    assert resp.status_code == 404
    assert resume_recorder == {}          # graph untouched
    assert slack_recorder == {}           # nothing sent


def test_send_without_nudge_text_is_422(client, seeded_approval, resume_recorder, slack_recorder):
    assert client.post(f"/approvals/{seeded_approval}/send").status_code == 422


def test_hold_resumes_with_request_changes_and_sends_nothing(
    client, db_session, seeded_approval, resume_recorder, slack_recorder
):
    resp = client.post(f"/approvals/{seeded_approval}/hold")

    assert resp.status_code == 200
    assert resp.json() == {"status": "held", "approval_id": "ap-1"}
    db_session.expire_all()
    assert db_session.get(Approval, "ap-1").status == "pending"  # unchanged
    assert slack_recorder == {}
    assert resume_recorder == {"deal_id": "deal-1", "action": "request_changes"}


def test_hold_missing_approval_is_404(client, resume_recorder):
    assert client.post("/approvals/nope/hold").status_code == 404
    assert resume_recorder == {}


def test_resolve_records_outcome_and_recomputes_momentum(
    client, db_session, seeded_approval, monkeypatch
):
    outcome_calls = {}

    def fake_record(db, deal_id, approver_id, actual_delay_days, artifact_format_used, delay_reason=""):
        outcome_calls.update(
            deal_id=deal_id,
            approver_id=approver_id,
            actual_delay_days=actual_delay_days,
            artifact_format_used=artifact_format_used,
            delay_reason=delay_reason,
        )

    monkeypatch.setattr("routes.approvals.record_outcome_sync", fake_record)
    monkeypatch.setattr("routes.approvals.compute_momentum_score", lambda db, deal_id: 85)

    resp = client.post(
        f"/approvals/{seeded_approval}/resolve",
        params={"actual_delay_days": 2.5, "artifact_format_used": "one-pager"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "approved", "new_momentum_score": 85}
    db_session.expire_all()
    row = db_session.get(Approval, "ap-1")
    assert row.status == "approved"
    assert row.actual_delay_days == 2.5
    assert outcome_calls["approver_id"] == "finance_raj"


def test_resolve_missing_approval_is_404(client, monkeypatch):
    outcome_calls = {}
    monkeypatch.setattr("routes.approvals.record_outcome_sync", lambda db, **kw: outcome_calls.update(kw))
    resp = client.post("/approvals/nope/resolve", params={"actual_delay_days": 1.0, "artifact_format_used": "x"})
    assert resp.status_code == 404
    assert outcome_calls == {}


def test_resolve_missing_required_params_is_422(client, seeded_approval):
    assert client.post(f"/approvals/{seeded_approval}/resolve").status_code == 422
