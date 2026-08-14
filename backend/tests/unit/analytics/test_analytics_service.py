"""Unit tests for analytics domain objects and service logic."""

import pytest

from app.application.analytics.analytics_service import AnalyticsService
from app.domain.analytics.entities import Evidence, Insight, MetricDefinition, TrendPoint


class TestEvidence:
    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValueError):
            Evidence(source_table="t", description="d", confidence=1.5)

    def test_valid_confidence(self) -> None:
        evidence = Evidence(source_table="fact_billing", description="revenue", confidence=0.9)
        assert evidence.confidence == 0.9
        assert evidence.metric is None


class TestInsight:
    def test_valid_insight(self) -> None:
        insight = Insight(
            insight_id="ins_1",
            metric="arpu",
            title="ARPU increased",
            value=75.2,
            change_rate=0.047,
            trend="up",
            confidence=0.9,
        )
        assert insight.trend == "up"

    def test_invalid_trend_rejected(self) -> None:
        with pytest.raises(ValueError):
            Insight(insight_id="ins_1", metric="arpu", title="x", trend="sideways")

    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValueError):
            Insight(insight_id="ins_1", metric="arpu", title="x", confidence=2.0)


class TestMetricDefinition:
    def test_defaults(self) -> None:
        definition = MetricDefinition(
            metric_name="arpu",
            category="revenue",
            business_definition="Average revenue per user",
            formula="SUM(net_revenue) / COUNT(DISTINCT customer_id)",
        )
        assert definition.unit == ""
        assert definition.version == "v1.0.0"


class TestTrendStats:
    def test_upward_trend(self) -> None:
        series = [
            TrendPoint(period=f"2026-{m:02d}", value=float(10 + i))
            for i, m in enumerate(range(1, 7))
        ]
        direction, slope = AnalyticsService._trend_stats(series)
        assert direction == "up"
        assert slope > 0

    def test_downward_trend(self) -> None:
        series = [
            TrendPoint(period=f"2026-{m:02d}", value=float(50 - i * 5))
            for i, m in enumerate(range(1, 7))
        ]
        direction, _ = AnalyticsService._trend_stats(series)
        assert direction == "down"

    def test_stable_trend(self) -> None:
        series = [TrendPoint(period=f"2026-{m:02d}", value=42.0) for m in range(1, 7)]
        direction, _ = AnalyticsService._trend_stats(series)
        assert direction == "stable"

    def test_short_series_stable(self) -> None:
        series = [TrendPoint(period="2026-01", value=10.0)]
        direction, _ = AnalyticsService._trend_stats(series)
        assert direction == "stable"


class TestZScoreAnomalies:
    def test_no_anomaly_in_flat_series(self) -> None:
        series = [TrendPoint(period=f"m{i}", value=50.0) for i in range(8)]
        anomalies = AnalyticsService._zscore_anomalies("arpu", series)
        assert anomalies == []

    def test_detects_spike(self) -> None:
        series = [TrendPoint(period=f"m{i}", value=50.0) for i in range(7)]
        series.append(TrendPoint(period="m7", value=500.0))  # huge spike
        anomalies = AnalyticsService._zscore_anomalies("arpu", series)
        assert len(anomalies) == 1
        assert anomalies[0].metric == "arpu"
        assert anomalies[0].severity in ("MEDIUM", "HIGH")

    def test_insufficient_data(self) -> None:
        series = [TrendPoint(period=f"m{i}", value=float(i)) for i in range(3)]
        assert AnalyticsService._zscore_anomalies("arpu", series) == []
