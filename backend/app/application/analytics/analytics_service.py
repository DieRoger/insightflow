"""Analytics application service — KPI computation, trends, anomalies.

Reads from the Semantic Layer / Warehouse only through repositories
(AR-055 — no SQL in application services). Never writes data (AR-062).
Computes metrics from the Metric Registry — never invents definitions
(AR-043).
"""

import math
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.analytics.entities import Anomaly, MetricDefinition, TrendPoint
from app.domain.analytics.interfaces import KpiRepository, MetricRegistry

logger = get_logger(__name__)

# KPI values that live in the semantic materialized views
SEMANTIC_METRICS = {"arpu", "mrr", "revenue_growth_rate"}


class AnalyticsService:
    """Coordinates KPI and trend computation for the analytics API."""

    def __init__(
        self, session: AsyncSession, metric_registry: MetricRegistry, kpi_repo: KpiRepository
    ) -> None:
        self._session = session
        self._metrics = metric_registry
        self._kpi = kpi_repo

    # ------------------------------------------------------------------
    # KPI list
    # ------------------------------------------------------------------
    async def list_kpis(
        self,
        metric: str | None = None,
        category: str | None = None,
        region: str | None = None,
        period: str = "2026-07",
    ) -> list[dict[str, object]]:
        """Return KPI items per 05_API_SPEC §6.1."""
        definitions = await self._metrics.list(category)
        if metric:
            definitions = [d for d in definitions if d.metric_name == metric]

        items: list[dict[str, object]] = []
        for definition in definitions:
            value = await self._compute_kpi(definition, region, period)
            if value is None:
                continue
            items.append(
                {
                    "metric_name": definition.metric_name,
                    "category": definition.category,
                    "value": round(value, 4),
                    "unit": definition.unit,
                    "previous_value": None,
                    "change_rate": None,
                    "trend": None,
                    "region": region,
                    "period": period,
                }
            )
        return items

    # ------------------------------------------------------------------
    # Single metric trend
    # ------------------------------------------------------------------
    async def get_metric_trend(
        self,
        metric_name: str,
        granularity: str = "month",
        periods: int = 12,
    ) -> dict[str, object] | None:
        """Return trend series for one metric per 05_API_SPEC §6.2."""
        definition = await self._metrics.get(metric_name)
        if definition is None:
            return None

        if metric_name in SEMANTIC_METRICS:
            series = await self._kpi.semantic_trend(metric_name, periods)
        else:
            series = await self._kpi.warehouse_trend(metric_name)

        if not series:
            return None

        direction, slope = self._trend_stats(series)
        return {
            "metric_name": metric_name,
            "unit": definition.unit,
            "granularity": granularity,
            "series": [{"period": p.period, "value": round(p.value, 4)} for p in series],
            "trend": {
                "direction": direction,
                "slope": round(slope, 6),
                "confidence": round(min(0.5 + abs(slope) * 10, 0.95), 4),
            },
            "anomalies": [],
        }

    # ------------------------------------------------------------------
    # Anomalies
    # ------------------------------------------------------------------
    async def list_anomalies(
        self, metric: str | None = None, limit: int = 20
    ) -> list[dict[str, object]]:
        """Detect anomalies on key metrics using z-score (05_API_SPEC §6.4)."""
        anomalies: list[Anomaly] = []
        target_metrics = [metric] if metric else ["arpu", "mrr", "churn_rate"]

        for metric_name in target_metrics:
            series = await self._kpi.semantic_trend(metric_name, 12)
            if len(series) < 5:
                continue
            anomalies.extend(self._zscore_anomalies(metric_name, series))

        anomalies.sort(key=lambda a: a.observed, reverse=True)
        return [
            {
                "anomaly_id": a.anomaly_id,
                "metric": a.metric,
                "region": a.region,
                "observed": round(a.observed, 4),
                "expected": round(a.expected, 4),
                "deviation_pct": round(a.deviation_pct, 2),
                "severity": a.severity,
                "detected_at": a.detected_at.isoformat(),
            }
            for a in anomalies[:limit]
        ]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    async def _compute_kpi(
        self, definition: MetricDefinition, region: str | None, period: str
    ) -> float | None:
        """Compute one KPI from the semantic layer or warehouse."""
        try:
            year, month = (int(part) for part in period.split("-"))
        except (ValueError, AttributeError):
            return None

        if definition.metric_name in SEMANTIC_METRICS:
            return await self._kpi.semantic_value(definition.metric_name, region, year, month)
        return await self._kpi.warehouse_value(definition.metric_name, region)

    @staticmethod
    def _trend_stats(series: list[TrendPoint]) -> tuple[str, float]:
        """Compute direction and slope via least-squares linear regression."""
        if len(series) < 2:
            return "stable", 0.0
        xs = list(range(len(series)))
        ys = [p.value for p in series]
        n = len(xs)
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
        denominator = sum((x - mean_x) ** 2 for x in xs)
        slope = numerator / denominator if denominator else 0.0
        if slope > 0.02 * abs(mean_y or 1):
            return "up", slope
        if slope < -0.02 * abs(mean_y or 1):
            return "down", slope
        return "stable", slope

    @staticmethod
    def _zscore_anomalies(metric_name: str, series: list[TrendPoint]) -> list[Anomaly]:
        """Detect anomalies via z-score (|z| > 2 → anomaly)."""
        if len(series) < 5:
            return []
        values = [p.value for p in series]
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = math.sqrt(variance) if variance else 0.0

        detected: list[Anomaly] = []
        for point in series:
            if std == 0:
                continue
            z = (point.value - mean) / std
            if abs(z) < 2:
                continue
            deviation = ((point.value - mean) / mean * 100) if mean else 0.0
            severity = "HIGH" if abs(z) >= 3 else "MEDIUM"
            detected.append(
                Anomaly(
                    anomaly_id=f"ano_{uuid.uuid4().hex[:8]}",
                    metric=metric_name,
                    observed=point.value,
                    expected=round(mean, 4),
                    deviation_pct=round(deviation, 2),
                    severity=severity,
                )
            )
        return detected
