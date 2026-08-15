"""Dataset Profiling — descriptive statistics for any incoming dataset.

Complements the Data Quality layer (quality.py): quality answers "does the
data pass the rules?" while profiling answers "what does the data look like?"
Per the data plan §2, profiling runs on the Raw → Canonical boundary before
quality gating.

Output is a structured ProfilingReport:
  - dataset identity + shape
  - per-column numeric stats (describe: min/max/mean/std/quantiles)
  - missing value counts + ratios
  - cardinality / unique counts
  - numeric distribution buckets (equal-width histogram)
  - categorical top values
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@dataclass
class NumericStats:
    """Descriptive statistics for a numeric column."""

    column: str
    dtype: str
    count: int
    missing: int
    missing_ratio: float
    unique: int
    min: float | None = None
    max: float | None = None
    mean: float | None = None
    std: float | None = None
    p25: float | None = None
    p50: float | None = None
    p75: float | None = None
    histogram: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "column": self.column,
            "dtype": self.dtype,
            "count": self.count,
            "missing": self.missing,
            "missing_ratio": round(self.missing_ratio, 4),
            "unique": self.unique,
            "min": self.min,
            "max": self.max,
            "mean": self.mean,
            "std": self.std,
            "p25": self.p25,
            "p50": self.p50,
            "p75": self.p75,
            "histogram": self.histogram,
        }


@dataclass
class CategoricalStats:
    """Frequency stats for a categorical / object column."""

    column: str
    dtype: str
    count: int
    missing: int
    missing_ratio: float
    unique: int
    top_values: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "column": self.column,
            "dtype": self.dtype,
            "count": self.count,
            "missing": self.missing,
            "missing_ratio": round(self.missing_ratio, 4),
            "unique": self.unique,
            "top_values": self.top_values,
        }


@dataclass
class ProfilingReport:
    """Structured profiling result for one dataset."""

    dataset_id: str
    rows: int
    columns: int
    numeric: list[NumericStats] = field(default_factory=list)
    categorical: list[CategoricalStats] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "rows": self.rows,
            "columns": self.columns,
            "numeric": [s.to_dict() for s in self.numeric],
            "categorical": [s.to_dict() for s in self.categorical],
        }


def _numeric_stats(column: str, s: pd.Series) -> NumericStats:
    """Describe one numeric column (excluding NaN)."""
    clean = pd.to_numeric(s, errors="coerce").dropna()
    n = len(s)
    missing = int(s.isna().sum()) + int((n - len(clean)) - s.isna().sum())  # non-coercible count
    missing_ratio = missing / n if n else 0.0

    stats = NumericStats(
        column=column,
        dtype=str(s.dtype),
        count=len(clean),
        missing=missing,
        missing_ratio=missing_ratio,
        unique=int(clean.nunique()),
    )

    if len(clean) == 0:
        return stats

    desc = clean.describe()
    stats.min = _safe_float(desc.get("min"))
    stats.max = _safe_float(desc.get("max"))
    stats.mean = _safe_float(desc.get("mean"))
    stats.std = _safe_float(desc.get("std"))
    stats.p25 = _safe_float(desc.get("25%"))
    stats.p50 = _safe_float(desc.get("50%"))
    stats.p75 = _safe_float(desc.get("75%"))

    stats.histogram = _histogram(clean)
    return stats


def _categorical_stats(column: str, s: pd.Series) -> CategoricalStats:
    """Describe one categorical column (top values + counts)."""
    n = len(s)
    missing = int(s.isna().sum())
    missing_ratio = missing / n if n else 0.0
    non_null = s.dropna()

    stats = CategoricalStats(
        column=column,
        dtype=str(s.dtype),
        count=len(non_null),
        missing=missing,
        missing_ratio=missing_ratio,
        unique=int(non_null.nunique()),
    )
    # top 10 values by frequency
    top = non_null.value_counts().head(10)
    stats.top_values = [
        {"value": _safe_scalar(v), "count": int(c), "ratio": round(int(c) / n, 4) if n else 0.0}
        for v, c in top.items()
    ]
    return stats


def _histogram(clean: pd.Series, buckets: int = 10) -> list[dict[str, Any]]:
    """Equal-width histogram of a numeric series."""
    if len(clean) < 2:
        return []
    lo, hi = float(clean.min()), float(clean.max())
    if lo == hi:
        return [{"min": lo, "max": hi, "count": len(clean)}]
    width = (hi - lo) / buckets
    edges = [lo + i * width for i in range(buckets + 1)]
    counts, _ = np.histogram(clean, bins=edges)
    return [
        {"min": round(edges[i], 4), "max": round(edges[i + 1], 4), "count": int(counts[i])}
        for i in range(buckets)
    ]


def profile_dataframe(df: pd.DataFrame, dataset_id: str) -> ProfilingReport:
    """Profile a DataFrame — split columns into numeric vs categorical."""
    report = ProfilingReport(dataset_id=dataset_id, rows=len(df), columns=df.shape[1])
    for col in df.columns:
        s = df[col]
        if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
            report.numeric.append(_numeric_stats(col, s))
        else:
            report.categorical.append(_categorical_stats(col, s))
    return report


def _safe_float(v: Any) -> float | None:
    try:
        f = float(v)
        return None if np.isnan(f) or np.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _safe_scalar(v: Any) -> Any:
    """Convert numpy scalars to plain Python for JSON serialization."""
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v
