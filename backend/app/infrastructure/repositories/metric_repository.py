"""PostgreSQL implementation of the MetricRegistry interface."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.analytics.entities import MetricDefinition
from app.domain.analytics.interfaces import MetricRegistry


class MetricRepository(MetricRegistry):
    """Reads metric definitions from semantic.metric_registry."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, metric_name: str) -> MetricDefinition | None:
        result = await self._session.execute(
            text(
                "SELECT metric_name, category, business_definition, formula, unit, "
                "data_source, refresh_cron, owner, version "
                "FROM semantic.metric_registry WHERE metric_name = :name"
            ),
            {"name": metric_name},
        )
        row = result.fetchone()
        if row is None:
            return None
        return self._to_entity(row)

    async def list(self, category: str | None = None) -> list[MetricDefinition]:
        if category:
            result = await self._session.execute(
                text(
                    "SELECT metric_name, category, business_definition, formula, unit, "
                    "data_source, refresh_cron, owner, version "
                    "FROM semantic.metric_registry WHERE category = :category "
                    "AND NOT is_deprecated ORDER BY metric_name"
                ),
                {"category": category},
            )
        else:
            result = await self._session.execute(
                text(
                    "SELECT metric_name, category, business_definition, formula, unit, "
                    "data_source, refresh_cron, owner, version "
                    "FROM semantic.metric_registry WHERE NOT is_deprecated "
                    "ORDER BY metric_name"
                )
            )
        return [self._to_entity(row) for row in result.fetchall()]

    @staticmethod
    def _to_entity(row: Any) -> MetricDefinition:
        return MetricDefinition(
            metric_name=row[0],
            category=row[1],
            business_definition=row[2],
            formula=row[3],
            unit=row[4] or "",
            data_source=row[5] or "",
            refresh_cron=row[6] or "",
            owner=row[7] or "",
            version=row[8],
        )
