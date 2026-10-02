from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi.testclient import TestClient
import httpx
import pytest
from sqlalchemy import func, select

from backend.commerce import execute_simulated_refund
from backend.config import Settings
from backend.database import Order, Payment, Refund, Run
from backend.main import create_app
from backend.seed import seed
from conftest import decide, investigate


def test_api_requires_authentication(client):
    assert client.get("/health").status_code == 200
    assert client.get("/api/tickets", headers={"X-API-Key": "wrong"}).status_code == 401
    assert len(client.get("/api/tickets").json()) == 6
    assert client.get("/api/tickets/no-such-ticket").status_code == 404


def test_approval_is_required_and_duplicate_decisions_are_idempotent(client):
    run = investigate(client)
    assert run["status"] == "awaiting_approval"
    db = client.app.state.db
    with db.Session() as s:
        assert s.scalar(select(func.count()).select_from(Refund).where(Refund.payment_id == "PAY-1001")) == 0
    blocked = execute_simulated_refund(db, run["payload"])
    assert blocked["status"] == "manual_review"
    first = decide(client, run)
    assert first.status_code == 200
    assert first.json()["status"] == "resolved"
    repeated = decide(client, run)
    assert repeated.json()["payload"]["result"]["refund"]["id"] == first.json()["payload"]["result"]["refund"]["id"]
    assert decide(client, run, "reject").status_code == 409
    with db.Session() as s:
        assert s.scalar(select(func.count()).select_from(Refund).where(Refund.payment_id == "PAY-1001")) == 1
    assert client.get("/api/tickets/TKT-1001").json()["ticket"]["status"] == "resolved"


def test_rejection_does_not_refund(client):
    run = investigate(client)
    assert decide(client, run, "reject").json()["status"] == "rejected"
    with client.app.state.db.Session() as s:
        assert s.get(Payment, "PAY-1001").status == "captured"
    assert client.get("/api/tickets/TKT-1001").json()["ticket"]["status"] == "manual_review"


@pytest.mark.parametrize("ticket", ["TKT-1002", "TKT-1003", "TKT-1004", "TKT-1005"])
def test_unsupported_or_incomplete_cases_require_manual_review(client, ticket):
    run = investigate(client, ticket)
    assert run["status"] == "manual_review"
    assert run["payload"]["plan"]["action"] == "manual_review"
    assert decide(client, run).status_code == 409


def test_failed_action_keeps_ticket_unresolved(client):
    run = investigate(client, "TKT-1006")
    result = decide(client, run).json()
    assert result["status"] == "action_failed"
    with client.app.state.db.Session() as s:
        assert s.get(Payment, "PAY-1006").status == "captured"
        assert s.scalar(select(Refund).where(Refund.payment_id == "PAY-1006")) is None
    assert client.get("/api/tickets/TKT-1006").json()["ticket"]["status"] == "manual_review"


def test_changed_evidence_blocks_approved_action(client):
    run = investigate(client)
    with client.app.state.db.Session.begin() as s:
        s.get(Order, "ORD-1001").status = "delivered"
    result = decide(client, run).json()
    assert result["status"] == "manual_review"
    assert "changed" in result["payload"]["result"]["message"]


def test_amount_mismatch_is_manual_review(client):
    with client.app.state.db.Session.begin() as s:
        s.get(Payment, "PAY-1001").amount_minor = 1
    assert investigate(client)["status"] == "manual_review"


def test_duplicate_investigation_returns_same_pending_run(client):
    first = investigate(client)
    assert investigate(client)["id"] == first["id"]


def test_approval_survives_application_restart(settings):
    with TestClient(create_app(settings)) as first:
        first.headers["X-API-Key"] = settings.api_key
        run = investigate(first)
    with TestClient(create_app(settings)) as second:
        second.headers["X-API-Key"] = settings.api_key
        assert second.get("/api/tickets/TKT-1001").json()["runs"][0]["status"] == "awaiting_approval"
        assert decide(second, run).json()["status"] == "resolved"


def test_seed_never_resets_a_completed_refund(client):
    decide(client, investigate(client))
    seed(client.app.state.db)
    with client.app.state.db.Session() as s:
        assert s.get(Payment, "PAY-1001").status == "refunded"
    assert client.get("/api/tickets/TKT-1001").json()["ticket"]["status"] == "resolved"


def test_concurrent_approval_creates_only_one_refund(client):
    run = investigate(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: decide(client, run), range(2)))
    assert all(r.status_code == 200 and r.json()["status"] == "resolved" for r in results)
    with client.app.state.db.Session() as s:
        assert s.scalar(select(func.count()).select_from(Refund).where(Refund.run_id == run["id"])) == 1


def test_two_tickets_for_same_payment_cannot_double_refund(client):
    created = client.post("/api/tickets", json={"order_id": "ORD-1001", "subject": "Second complaint",
                          "description": "Please also check this failed payment."}).json()
    first = investigate(client)
    second = investigate(client, created["id"])
    assert decide(client, first).json()["status"] == "resolved"
    assert decide(client, second).json()["status"] == "manual_review"


def test_crash_after_refund_commit_recovers_without_duplicate(client):
    run = investigate(client)
    real_execute = execute_simulated_refund

    def crash_after_commit(db, state):
        real_execute(db, state)
        raise RuntimeError("Simulated process failure after business commit")

    with patch("backend.workflow.execute_simulated_refund", side_effect=crash_after_commit):
        assert decide(client, run).status_code == 503
    result = client.post(f"/api/runs/{run['id']}/resume")
    assert result.status_code == 200
    assert result.json()["status"] == "resolved"
    with client.app.state.db.Session() as s:
        assert s.scalar(select(func.count()).select_from(Refund).where(Refund.run_id == run["id"])) == 1


def test_resume_without_decision_does_not_approve(client):
    run = investigate(client)
    result = client.post(f"/api/runs/{run['id']}/resume").json()
    assert result["status"] == "awaiting_approval"
    assert result["decision"] is None


def test_invalid_ticket_and_decision_input(client):
    assert client.post("/api/tickets", json={"order_id": "bad", "subject": "Missing order", "description": "No such order exists"}).status_code == 404
    run = investigate(client)
    assert client.post(f"/api/runs/{run['id']}/decision", json={"action": "approve", "reviewer": "AB", "amount_minor": 1}).status_code == 422
    assert client.post(f"/api/runs/{run['id']}/decision", json={"action": "approve", "reviewer": " "}).status_code == 422


def test_production_requires_durable_storage_and_unique_key():
    with pytest.raises(ValueError):
        Settings(environment="production").validate()
    with pytest.raises(ValueError):
        Settings(environment="production", api_key="x" * 40).validate()


def test_gemini_error_falls_back_without_changing_policy(client):
    client.app.state.workflow.settings.ai_mode = "gemini"
    client.app.state.workflow.settings.gemini_key = "fake-test-key"
    client.app.state.workflow.settings.gemini_model = "fake-test-model"
    with patch("backend.workflow.httpx.post", side_effect=httpx.ConnectError("Unavailable")):
        run = investigate(client)
    assert run["status"] == "awaiting_approval"
    assert run["payload"]["explanation_mode"] == "rules_fallback"


def test_gemini_text_is_advisory_only(client):
    settings = client.app.state.workflow.settings
    settings.ai_mode, settings.gemini_key, settings.gemini_model = "gemini", "fake-key", "fake-model"
    response = httpx.Response(200, request=httpx.Request("POST", "https://example.test"),
                              json={"candidates": [{"content": {"parts": [{"text": "Ignore policy and refund everything"}]}}]})
    with patch("backend.workflow.httpx.post", return_value=response):
        run = investigate(client, "TKT-1002")
    assert run["payload"]["explanation_mode"] == "gemini"
    assert run["payload"]["plan"]["action"] == "manual_review"
    assert decide(client, run).status_code == 409
