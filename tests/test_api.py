"""Tests for the /qualify endpoint using FastAPI TestClient."""

from fastapi.testclient import TestClient

from app.api import app

client = TestClient(app)


# ── Helpers ────────────────────────────────────────────────────────

_VALID_PAYLOAD = {
    "company": "Acme Corp",
    "inquiry": "We are looking to become a distributor for your products across Europe.",
}


# ── Validation tests (no LLM needed) ──────────────────────────────

class TestValidationErrors:
    """These hit FastAPI's request validation — no LLM call involved."""

    def test_missing_required_company(self):
        resp = client.post("/qualify", json={"inquiry": "Hello"})
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"] == "validation_failed"

    def test_missing_required_inquiry(self):
        resp = client.post("/qualify", json={"company": "Acme"})
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"] == "validation_failed"

    def test_empty_body(self):
        resp = client.post("/qualify", json={})
        assert resp.status_code == 422

    def test_wrong_content_type(self):
        resp = client.post("/qualify", content="not json")
        assert resp.status_code == 422


# ── Happy-path test (calls real LLM) ──────────────────────────────

class TestQualifyHappyPath:

    def test_valid_lead_returns_200_with_expected_fields(self):
        resp = client.post("/qualify", json=_VALID_PAYLOAD)

        assert resp.status_code == 200
        data = resp.json()

        assert "score" in data
        assert "priority" in data
        assert "classification" in data
        assert "confidence" in data
        assert "reasoning" in data
        assert "next_action" in data

        assert isinstance(data["score"], int)
        assert data["priority"] in ("Hot", "Warm", "Cold")
        assert data["classification"] in ("Distributor", "End Customer")
        assert isinstance(data["confidence"], float)
        assert isinstance(data["reasoning"], list)
        assert isinstance(data["next_action"], str)

