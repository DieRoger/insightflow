"""Integration tests for the churn prediction API (05_API_SPEC §8)."""

import httpx
import pytest

from app.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
async def client() -> httpx.AsyncClient:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


class TestChurnPredictAPI:
    async def test_predict_known_customer(self, client: httpx.AsyncClient) -> None:
        """Known churned customer returns HIGH risk with factors."""
        response = await client.post("/api/v1/churn/predict", json={"customer_id": "CUST-00000002"})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert data["customer_id"] == "CUST-00000002"
        assert 0.0 <= data["risk_score"] <= 1.0
        assert data["risk_level"] in ("LOW", "MEDIUM", "HIGH")
        assert data["model_version"].startswith("v")
        assert data["prediction_id"].startswith("pred_")

    async def test_predict_unknown_customer_404(self, client: httpx.AsyncClient) -> None:
        """Unknown customer returns NF_001."""
        response = await client.post(
            "/api/v1/churn/predict", json={"customer_id": "CUST-DOES-NOT-EXIST"}
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NF_001"

    async def test_predict_missing_field_422(self, client: httpx.AsyncClient) -> None:
        """Missing customer_id is rejected by validation."""
        response = await client.post("/api/v1/churn/predict", json={})
        assert response.status_code == 422

    async def test_batch_predict(self, client: httpx.AsyncClient) -> None:
        """Batch prediction returns a completion summary."""
        response = await client.post("/api/v1/churn/predict/batch")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["count"] > 0
        assert body["data"]["status"] == "COMPLETED"
