"""Integration tests for the /system endpoints (Walking Skeleton).

These tests verify the full chain: HTTP request → FastAPI router →
response envelope with request_id.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    """Build a fresh app per test."""
    with TestClient(create_app()) as test_client:
        yield test_client


class TestHealthEndpoint:
    def test_health_returns_success_envelope(self, client: TestClient) -> None:
        """GET /api/v1/system/health returns the standard success envelope."""
        response = client.get("/api/v1/system/health")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["status"] in ("healthy", "degraded")
        assert body["data"]["version"] == "0.1.0"
        assert body["data"]["checks"]["database"] in ("ok", "degraded")
        assert body["request_id"].startswith("req_")

    def test_health_echoes_request_id_header(self, client: TestClient) -> None:
        """Client-supplied X-Request-ID is echoed back."""
        response = client.get("/api/v1/system/health", headers={"X-Request-ID": "req_test_123"})

        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == "req_test_123"
        assert response.json()["request_id"] == "req_test_123"


class TestMetricsEndpoint:
    def test_metrics_returns_success_envelope(self, client: TestClient) -> None:
        """GET /api/v1/system/metrics returns the standard success envelope."""
        response = client.get("/api/v1/system/metrics")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["requests_total"] == 0
        assert body["request_id"].startswith("req_")


class TestStandardErrorEnvelope:
    def test_unknown_endpoint_returns_standard_error(self, client: TestClient) -> None:
        """404 responses use the standard error envelope, not FastAPI default."""
        response = client.get("/api/v1/nonexistent")

        assert response.status_code == 404
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "NF_099"
        assert body["error"]["category"] == "NOT_FOUND"
        assert body["request_id"].startswith("req_")

    def test_method_not_allowed_returns_standard_error(self, client: TestClient) -> None:
        """405 responses use the standard error envelope."""
        response = client.post("/api/v1/system/health")

        assert response.status_code == 405
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "VAL_005"
        assert body["request_id"].startswith("req_")
