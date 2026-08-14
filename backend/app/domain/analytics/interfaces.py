"""Analytics repository interfaces (domain-facing, framework-independent).

Repositories return domain entities only — never ORM objects (AR-052).
"""

from abc import ABC, abstractmethod

from app.domain.analytics.entities import MetricDefinition, TrendPoint


class MetricRegistry(ABC):
    """Authoritative source of metric definitions (AR-013)."""

    @abstractmethod
    async def get(self, metric_name: str) -> MetricDefinition | None:
        """Retrieve a metric definition by name."""

    @abstractmethod
    async def list(self, category: str | None = None) -> list[MetricDefinition]:
        """List all metric definitions, optionally filtered by category."""


class KpiRepository(ABC):
    """Read-only access to pre-aggregated KPI values (AR-055).

    All KPI SQL lives behind this repository — application services and
    routers never execute SQL directly.
    """

    @abstractmethod
    async def semantic_value(
        self, metric_name: str, region: str | None, year: int, month: int
    ) -> float | None:
        """Read one pre-aggregated value from the semantic materialized views."""

    @abstractmethod
    async def semantic_trend(self, metric_name: str, periods: int) -> list[TrendPoint]:
        """Build a trend series from the semantic views (most recent first)."""

    @abstractmethod
    async def warehouse_value(self, metric_name: str, region: str | None) -> float | None:
        """Compute one metric directly from warehouse tables."""

    @abstractmethod
    async def warehouse_trend(self, metric_name: str) -> list[TrendPoint]:
        """Build a trend series directly from warehouse (fallback)."""
