"""Analytics domain objects — Insight, Evidence, MetricDefinition.

These are the universal language between analytics, AI, and reporting
(02_ARCHITECTURE.md §5, 07_AI_DESIGN.md §5). The domain layer imports
nothing from frameworks.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Evidence:
    """Reproducible supporting evidence for an insight.

    Must be reproducible — no hidden calculations (03_DATABASE.md §14).
    """

    source_table: str
    description: str
    metric: str | None = None
    sql: str | None = None
    sample_size: int | None = None
    confidence: float = 1.0
    generated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")


@dataclass(frozen=True)
class Insight:
    """Structured analytical finding with linked evidence (AR-022)."""

    insight_id: str
    metric: str
    title: str
    value: float | None = None
    baseline: float | None = None
    change_rate: float | None = None
    trend: str | None = None  # "up" | "down" | "stable"
    dimension: str | None = None
    evidence: list[Evidence] = field(default_factory=list)
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")
        if self.trend not in (None, "up", "down", "stable"):
            raise ValueError(f"invalid trend: {self.trend}")


@dataclass(frozen=True)
class MetricDefinition:
    """A registered business metric (AR-013 — one definition per metric)."""

    metric_name: str
    category: str
    business_definition: str
    formula: str
    unit: str = ""
    data_source: str = ""
    refresh_cron: str = ""
    owner: str = ""
    version: str = "v1.0.0"


@dataclass(frozen=True)
class TrendPoint:
    """A single point in a metric trend series."""

    period: str
    value: float


@dataclass(frozen=True)
class TrendSummary:
    """Directional trend summary for a metric."""

    direction: str  # "up" | "down" | "stable"
    slope: float
    confidence: float


@dataclass(frozen=True)
class Anomaly:
    """A detected anomaly on a monitored metric."""

    anomaly_id: str
    metric: str
    region: str | None = None
    observed: float = 0.0
    expected: float = 0.0
    deviation_pct: float = 0.0
    severity: str = "LOW"  # LOW | MEDIUM | HIGH
    detected_at: datetime = field(default_factory=datetime.utcnow)
