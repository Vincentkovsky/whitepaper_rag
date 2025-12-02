from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from app.api.routes import qa


class StubRAGService:
    def query(self, **kwargs):
        return {"answer": "hello", "cached": False, "model_used": kwargs.get("model")}


@pytest.fixture(autouse=True)
def override_dependencies(client):
    app = client.app
    app.dependency_overrides[qa.get_rag_service_dep] = lambda: StubRAGService()
    app.dependency_overrides[qa.get_subscription_service_dep] = lambda: app.state.test_subscription
    yield
    app.dependency_overrides.pop(qa.get_rag_service_dep, None)
    app.dependency_overrides.pop(qa.get_subscription_service_dep, None)


def test_qa_query_consumes_credits(client):
    token = "qa-user"
    resp = client.post(
        "/api/qa/query",
        headers={"Authorization": f"Bearer {token}"},
        json={"document_id": "doc1", "question": "hi"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["answer"] == "hello"


def test_qa_query_insufficient_credits(client):
    token = "qa-nocredit"
    sub = client.app.state.test_subscription
    ledger = sub._ledger(token)
    ledger.consumed = sub._monthly_quota(ledger.plan)
    resp = client.post(
        "/api/qa/query",
        headers={"Authorization": f"Bearer {token}"},
        json={"document_id": "doc1", "question": "hi"},
    )
    assert resp.status_code == 402


def test_analysis_generate_returns_gone(client):
    """Test that the deprecated analysis/generate endpoint returns 410 Gone."""
    token = "qa-analyst"
    resp = client.post(
        "/api/qa/analysis/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={"document_id": "doc2"},
    )
    assert resp.status_code == 410
    assert "X-Deprecation-Warning" in resp.headers
    payload = resp.json()
    assert "removed" in payload["detail"].lower()


def test_analysis_get_returns_gone(client):
    """Test that the deprecated analysis/{document_id} endpoint returns 410 Gone."""
    token = "qa-analyst"
    resp = client.get(
        "/api/qa/analysis/doc123",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 410
    assert "X-Deprecation-Warning" in resp.headers
    payload = resp.json()
    assert "removed" in payload["detail"].lower()
