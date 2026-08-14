"""PostgreSQL implementation of CustomerRepository."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.customer.entities import Customer, CustomerFilters, PaginatedResult
from app.domain.customer.interfaces import CustomerRepository

# Columns sortable in the customer list endpoint
SORTABLE_COLUMNS = {
    "tenure_days": "dc.join_date",  # tenure derived from join_date (older = longer tenure)
    "arpu": "cf.arpu",
    "clv": "dc.clv",
    "churn_risk": "pred.risk_score",
    "join_date": "dc.join_date",
}


class CustomerRepositorySQL(CustomerRepository):
    """Reads customers from warehouse.dim_customer (+ features + predictions)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, customer_id: int) -> Customer | None:
        result = await self._session.execute(
            text(
                """
                SELECT dc.customer_id, dc.source_customer_id, dc.status, dc.lifecycle_stage,
                       dc.join_date, dc.contract_type, dc.gender, dc.age, dc.city, dc.province,
                       dr.region_name, dp.package_name, dc.segment, dc.clv
                FROM warehouse.dim_customer dc
                LEFT JOIN warehouse.dim_region dr ON dc.region_id = dr.region_id
                LEFT JOIN warehouse.dim_package dp ON dc.package_id = dp.package_id
                WHERE dc.customer_id = :id
                """
            ),
            {"id": customer_id},
        )
        row = result.fetchone()
        if row is None:
            return None
        return self._to_entity(row)

    async def get_by_source_id(self, source_customer_id: str) -> Customer | None:
        result = await self._session.execute(
            text(
                """
                SELECT dc.customer_id, dc.source_customer_id, dc.status, dc.lifecycle_stage,
                       dc.join_date, dc.contract_type, dc.gender, dc.age, dc.city, dc.province,
                       dr.region_name, dp.package_name, dc.segment, dc.clv
                FROM warehouse.dim_customer dc
                LEFT JOIN warehouse.dim_region dr ON dc.region_id = dr.region_id
                LEFT JOIN warehouse.dim_package dp ON dc.package_id = dp.package_id
                WHERE dc.source_customer_id = :sid
                """
            ),
            {"sid": source_customer_id},
        )
        row = result.fetchone()
        if row is None:
            return None
        return self._to_entity(row)

    async def search(self, filters: CustomerFilters) -> PaginatedResult[Customer]:
        where: list[str] = []
        params: dict[str, object] = {
            "limit": filters.page_size,
            "offset": (filters.page - 1) * filters.page_size,
        }

        if filters.status:
            where.append("dc.status = :status")
            params["status"] = filters.status
        if filters.segment:
            where.append("dc.segment = :segment")
            params["segment"] = filters.segment
        if filters.lifecycle_stage:
            where.append("dc.lifecycle_stage = :lifecycle_stage")
            params["lifecycle_stage"] = filters.lifecycle_stage
        if filters.risk_level:
            where.append("pred.risk_level = :risk_level")
            params["risk_level"] = filters.risk_level
        if filters.region:
            where.append("dr.region_name = :region")
            params["region"] = filters.region
        if filters.search:
            where.append("dc.source_customer_id ILIKE :search")
            params["search"] = f"%{filters.search}%"

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        sort_col = SORTABLE_COLUMNS.get(filters.sort, "dc.tenure_days")
        order = "ASC" if filters.order.lower() == "asc" else "DESC"

        # Count
        count_result = await self._session.execute(
            text(
                f"""
                SELECT COUNT(*) FROM warehouse.dim_customer dc
                LEFT JOIN warehouse.dim_region dr ON dc.region_id = dr.region_id
                LEFT JOIN ml.prediction_registry pred ON pred.customer_id = dc.customer_id
                {where_sql}
                """
            ),
            params,
        )
        total = count_result.scalar() or 0

        # Rows
        result = await self._session.execute(
            text(
                f"""
                SELECT dc.customer_id, dc.source_customer_id, dc.status, dc.lifecycle_stage,
                       dc.join_date, dc.contract_type, dc.gender, dc.age, dc.city, dc.province,
                       dr.region_name, dp.package_name, dc.segment, dc.clv,
                       pred.risk_score
                FROM warehouse.dim_customer dc
                LEFT JOIN warehouse.dim_region dr ON dc.region_id = dr.region_id
                LEFT JOIN warehouse.dim_package dp ON dc.package_id = dp.package_id
                LEFT JOIN ml.prediction_registry pred ON pred.customer_id = dc.customer_id
                {where_sql}
                ORDER BY {sort_col} {order}
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
        items = [self._to_entity(row) for row in result.fetchall()]
        return PaginatedResult(
            items=items, page=filters.page, page_size=filters.page_size, total=total
        )

    @staticmethod
    def _to_entity(row: Any) -> Customer:
        risk_score = row[14] if len(row) > 14 else None
        return Customer(
            customer_id=row[0],
            source_customer_id=row[1],
            status=row[2],
            lifecycle_stage=row[3],
            join_date=row[4],
            contract_type=row[5],
            gender=row[6],
            age=row[7],
            city=row[8],
            province=row[9],
            region=row[10],
            package_name=row[11],
            segment=row[12],
            clv=float(row[13]) if row[13] is not None else None,
            risk_score=float(risk_score) if risk_score is not None else None,
        )

    # ------------------------------------------------------------------
    # Customer 360 profile sub-queries (05_API_SPEC §7.2)
    # ------------------------------------------------------------------
    async def get_usage_summary(
        self, customer_id: int
    ) -> tuple[float | None, float | None, float | None]:
        """Return (avg_daily_data_mb, avg_daily_voice_min, peak_usage_ratio)."""
        result = await self._session.execute(
            text(
                """
                SELECT AVG(data_usage_mb), AVG(voice_minutes),
                       AVG(peak_usage_mb / NULLIF(data_usage_mb, 0))
                FROM warehouse.fact_usage_daily WHERE customer_id = :id
                """
            ),
            {"id": customer_id},
        )
        row = result.fetchone()
        if row is None:
            return None, None, None
        return (
            float(row[0]) if row[0] is not None else None,
            float(row[1]) if row[1] is not None else None,
            float(row[2]) if row[2] is not None else None,
        )

    async def get_billing_summary(self, customer_id: int) -> tuple[float | None, str | None, int]:
        """Return (arpu, last_payment_status, overdue_days)."""
        result = await self._session.execute(
            text(
                """
                SELECT AVG(monthly_fee - discount_amount), MAX(payment_status), MAX(overdue_days)
                FROM warehouse.fact_billing WHERE customer_id = :id
                """
            ),
            {"id": customer_id},
        )
        row = result.fetchone()
        if row is None:
            return None, None, 0
        return (
            float(row[0]) if row[0] is not None else None,
            row[1] if row[1] is not None else None,
            int(row[2]) if row[2] is not None else 0,
        )

    async def get_service_summary(self, customer_id: int) -> tuple[int, float | None, float | None]:
        """Return (complaints_count, avg_csat, avg_resolution_time_min)."""
        result = await self._session.execute(
            text(
                """
                SELECT COUNT(*), AVG(csat_score), AVG(resolution_time_min)
                FROM warehouse.fact_service WHERE customer_id = :id
                """
            ),
            {"id": customer_id},
        )
        row = result.fetchone()
        if row is None:
            return 0, None, None
        return (
            int(row[0]) if row[0] else 0,
            float(row[1]) if row[1] is not None else None,
            float(row[2]) if row[2] is not None else None,
        )

    async def get_latest_prediction(self, customer_id: int) -> tuple[float | None, str | None]:
        """Return (risk_score, risk_level) for the most recent prediction."""
        result = await self._session.execute(
            text(
                """
                SELECT risk_score, risk_level FROM ml.prediction_registry
                WHERE customer_id = :id ORDER BY predicted_at DESC LIMIT 1
                """
            ),
            {"id": customer_id},
        )
        row = result.fetchone()
        if row is None:
            return None, None
        return (
            float(row[0]) if row[0] is not None else None,
            row[1] if row[1] is not None else None,
        )
