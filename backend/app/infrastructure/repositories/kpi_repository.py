"""PostgreSQL implementation of KpiRepository.

All KPI SQL lives here (AR-055) — application services and routers never
execute SQL directly.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.analytics.entities import TrendPoint
from app.domain.analytics.interfaces import KpiRepository


class KpiRepositorySQL(KpiRepository):
    """Reads KPI values from the semantic views and warehouse."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def semantic_value(
        self, metric_name: str, region: str | None, year: int, month: int
    ) -> float | None:
        params: dict[str, object] = {"year": year, "month": month}
        if metric_name == "arpu":
            sql = "SELECT AVG(arpu) FROM semantic.kpi_arpu WHERE year = :year AND month = :month"
            if region:
                sql += " AND region_name = :region"
                params["region"] = region
        elif metric_name == "mrr":
            sql = "SELECT mrr FROM semantic.kpi_revenue WHERE year = :year AND month = :month"
        elif metric_name == "revenue_growth_rate":
            sql = (
                "SELECT mrr_change / NULLIF(mrr - mrr_change, 0) FROM semantic.kpi_revenue "
                "WHERE year = :year AND month = :month"
            )
        else:
            return None

        result = await self._session.execute(text(sql), params)
        row = result.fetchone()
        return float(row[0]) if row and row[0] is not None else None

    async def semantic_trend(self, metric_name: str, periods: int) -> list[TrendPoint]:
        if metric_name == "arpu":
            sql = (
                "SELECT TO_CHAR(MAKE_DATE(year, month, 1), 'YYYY-MM') AS period, "
                "AVG(arpu) AS value "
                "FROM semantic.kpi_arpu GROUP BY year, month "
                "ORDER BY year, month DESC LIMIT :limit"
            )
        elif metric_name in ("mrr", "revenue_growth_rate"):
            sql = (
                "SELECT TO_CHAR(MAKE_DATE(year, month, 1), 'YYYY-MM') AS period, mrr AS value "
                "FROM semantic.kpi_revenue ORDER BY year, month DESC LIMIT :limit"
            )
        else:
            return []

        result = await self._session.execute(text(sql), {"limit": periods})
        series = [TrendPoint(period=r[0], value=float(r[1])) for r in result.fetchall()]
        series.reverse()
        return series

    async def warehouse_value(self, metric_name: str, region: str | None) -> float | None:
        sql = self._warehouse_sql(metric_name, region)
        if sql is None:
            return None
        result = await self._session.execute(text(sql))
        row = result.fetchone()
        return float(row[0]) if row and row[0] is not None else None

    async def warehouse_trend(self, metric_name: str) -> list[TrendPoint]:
        value = await self.warehouse_value(metric_name, None)
        if value is None:
            return []
        return [TrendPoint(period="current", value=value)]

    @staticmethod
    def _warehouse_sql(metric_name: str, region: str | None) -> str | None:
        """SQL for metrics computed directly from warehouse tables."""
        region_join = (
            "JOIN warehouse.dim_region dr ON dc.region_id = dr.region_id" if region else ""
        )

        formulas = {  # nosec B608: region_join is a constant string, no user values
            "active_customers": (
                "SELECT COUNT(DISTINCT dc.customer_id) FROM warehouse.dim_customer dc "
                f"{region_join} WHERE dc.status = 'active'"
            ),
            "churned_customers": (
                "SELECT COUNT(DISTINCT dc.customer_id) FROM warehouse.dim_customer dc "
                f"{region_join} WHERE dc.status = 'churned'"
            ),
            "churn_rate": (
                "SELECT COUNT(*) FILTER (WHERE dc.status = 'churned')::float "
                f"/ NULLIF(COUNT(*), 0) FROM warehouse.dim_customer dc {region_join}"
            ),
            "premium_customers": (
                "SELECT COUNT(DISTINCT dc.customer_id) FROM warehouse.dim_customer dc "
                "JOIN warehouse.dim_package dp ON dc.package_id = dp.package_id "
                f"{region_join} WHERE dp.package_type = 'premium'"
            ),
            "avg_latency": (
                "SELECT AVG(fn.latency_ms) FROM warehouse.fact_network fn "
                "WHERE fn.date_id = (SELECT MAX(date_id) FROM warehouse.fact_network)"
            ),
            "drop_rate": (
                "SELECT AVG(fn.drop_rate) FROM warehouse.fact_network fn "
                "WHERE fn.date_id = (SELECT MAX(date_id) FROM warehouse.fact_network)"
            ),
            "avg_daily_data": ("SELECT AVG(data_usage_mb) FROM warehouse.fact_usage_daily"),
        }
        return formulas.get(metric_name)
