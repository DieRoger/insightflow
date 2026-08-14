"""Integration tests for analytics + customer API endpoints against real PostgreSQL."""

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


class TestAnalyticsAPI:
    async def test_list_kpis_revenue_category(self, client: httpx.AsyncClient) -> None:
        """Revenue KPIs return ARPU with values."""
        response = await client.get(
            "/api/v1/analytics/kpi", params={"category": "revenue", "period": "2026-07"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert len(body["data"]["items"]) >= 1
        arpu = next((i for i in body["data"]["items"] if i["metric_name"] == "arpu"), None)
        assert arpu is not None
        assert arpu["value"] > 0
        assert arpu["unit"] == "USD"

    async def test_kpi_trend_returns_series(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/v1/analytics/kpi/arpu", params={"periods": 3})
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["series"]
        assert body["data"]["trend"]["direction"] in ("up", "down", "stable")

    async def test_kpi_trend_unknown_metric_404(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/v1/analytics/kpi/not_a_metric")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NF_001"

    async def test_anomaly_list(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/v1/analytics/anomaly")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "items" in body["data"]


class TestCustomerAPI:
    async def test_customer_list_paginated(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/v1/customers", params={"page": 1, "page_size": 5})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert len(body["data"]["items"]) <= 5
        assert body["meta"]["total"] > 0
        assert body["meta"]["total_pages"] >= 1

    async def test_customer_list_filters_status(self, client: httpx.AsyncClient) -> None:
        response = await client.get(
            "/api/v1/customers", params={"status": "active", "page_size": 5}
        )
        assert response.status_code == 200
        body = response.json()
        assert all(item["status"] == "active" for item in body["data"]["items"])

    async def test_customer_detail_360(self, client: httpx.AsyncClient) -> None:
        # Get first customer from list, then fetch full profile
        list_response = await client.get("/api/v1/customers", params={"page_size": 1})
        customer_id = list_response.json()["data"]["items"][0]["customer_id"]

        response = await client.get(f"/api/v1/customers/{customer_id}")
        assert response.status_code == 200
        body = response.json()
        data = body["data"]
        assert data["profile"]["customer_id"] == customer_id
        assert data["profile"]["status"] in ("active", "suspended", "churned")
        assert "billing" in data
        assert "usage" in data
        assert "service" in data
        assert "prediction" in data

    async def test_customer_detail_not_found(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/v1/customers/CUST-DOES-NOT-EXIST")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NF_001"

    async def test_customer_search(self, client: httpx.AsyncClient) -> None:
        list_response = await client.get("/api/v1/customers", params={"page_size": 1})
        customer_id = list_response.json()["data"]["items"][0]["customer_id"]
        response = await client.get("/api/v1/customers", params={"search": customer_id})
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["items"][0]["customer_id"] == customer_id
