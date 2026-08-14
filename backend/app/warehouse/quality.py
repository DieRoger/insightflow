"""Data Quality Layer — multi-dimensional validation for any dataset.

Per the data plan §5-6, every incoming dataset is scored on six dimensions:

  completeness          — null ratio per column
  validity              — value ranges / enum membership
  uniqueness            — duplicate keys
  consistency           — cross-column rules (e.g. total >= monthly)
  referential_integrity — FK references resolve
  overall_score         — weighted composite

Results are persisted to governance.quality_report + governance.quality_issue
and are used to decide whether a dataset is loadable into the canonical
schema (status: validated → loaded).
"""

import json
import sys
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.logging import get_logger  # noqa: E402

logger = get_logger(__name__)

# Severity levels for quality issues
SEVERITY_WEIGHT = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}


@dataclass
class ColumnRule:
    """A validation rule for one column."""

    column: str
    rule: str  # 'required' | 'non_negative' | 'enum' | 'date' | 'unique'
    values: list[str] | None = None  # for enum


@dataclass
class ConsistencyRule:
    """A cross-column consistency rule."""

    name: str
    expression: str  # pandas query string, must be False for bad rows
    description: str = ""


@dataclass
class QualityIssue:
    """A single quality issue found during validation."""

    column: str
    rule: str
    failed_count: int
    severity: str = "MEDIUM"
    samples: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DataQualityReport:
    """Result of validating one dataset."""

    dataset_id: str
    run_id: str
    rows_total: int
    rows_valid: int
    completeness: float = 100.0
    validity: float = 100.0
    uniqueness: float = 100.0
    consistency: float = 100.0
    referential_integrity: float = 100.0
    overall_score: float = 100.0
    issues: list[QualityIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "run_id": self.run_id,
            "rows_total": self.rows_total,
            "rows_valid": self.rows_valid,
            "completeness": self.completeness,
            "validity": self.validity,
            "uniqueness": self.uniqueness,
            "consistency": self.consistency,
            "referential_integrity": self.referential_integrity,
            "overall_score": self.overall_score,
        }


def _pct(ok: float, total: float) -> float:
    return round(ok / total * 100, 2) if total else 100.0


def run_quality_checks(
    df: pd.DataFrame,
    *,
    dataset_id: str,
    column_rules: list[ColumnRule],
    consistency_rules: list[ConsistencyRule] | None = None,
    unique_keys: list[str] | None = None,
    referential_checks: list[tuple[str, str, str]] | None = None,
    # referential_checks: list of (column, ref_schema, ref_table)
) -> DataQualityReport:
    """Run all quality checks against a dataframe.

    Args:
        df: the dataset to validate.
        dataset_id: registry id (e.g. IBM_TELCO_V1).
        column_rules: per-column validity rules.
        consistency_rules: cross-column rules (pandas query; False = bad).
        unique_keys: columns that must be unique (duplicates flagged).
        referential_checks: (column, ref_schema, ref_table) — reported but
            actual resolution happens against the warehouse (async).
    """
    run_id = f"run_{uuid.uuid4().hex[:10]}"
    report = DataQualityReport(
        dataset_id=dataset_id, run_id=run_id, rows_total=len(df), rows_valid=0
    )
    n = len(df)
    bad_mask = pd.Series(False, index=df.index)

    # 1. Completeness — non-null per required column
    for rule in column_rules:
        if rule.rule != "required":
            continue
        if rule.column not in df.columns:
            report.issues.append(
                QualityIssue(
                    column=rule.column,
                    rule="completeness",
                    failed_count=n,
                    severity="HIGH",
                    samples=[{}],
                )
            )
            bad_mask |= True
            continue
        missing = df[rule.column].isna()
        if missing.any():
            report.issues.append(
                QualityIssue(
                    column=rule.column,
                    rule="completeness",
                    failed_count=int(missing.sum()),
                    severity="MEDIUM" if missing.mean() < 0.05 else "HIGH",
                    samples=df.loc[missing, rule.column].head(5).to_dict(),
                )
            )
            bad_mask |= missing

    report.completeness = _pct(n - bad_mask.sum(), n)

    # 2. Validity — value ranges and enums
    invalid = pd.Series(False, index=df.index)
    for rule in column_rules:
        if rule.rule == "required" or rule.column not in df.columns:
            continue
        col = df[rule.column]
        if rule.rule == "non_negative" and pd.api.types.is_numeric_dtype(col):
            bad = col < 0
        elif rule.rule == "enum" and rule.values:
            bad = ~col.isin(rule.values)
        else:
            continue
        if bad.any():
            report.issues.append(
                QualityIssue(
                    column=rule.column,
                    rule="validity",
                    failed_count=int(bad.sum()),
                    severity="HIGH",
                    samples=df.loc[bad, rule.column].head(5).to_dict(),
                )
            )
            invalid |= bad

    report.validity = _pct(n - invalid.sum(), n)
    bad_mask |= invalid

    # 3. Uniqueness — duplicate keys
    if unique_keys:
        dup = df.duplicated(subset=unique_keys, keep=False)
        if dup.any():
            report.issues.append(
                QualityIssue(
                    column=",".join(unique_keys),
                    rule="uniqueness",
                    failed_count=int(dup.sum()),
                    severity="HIGH",
                    samples=df.loc[dup, unique_keys].head(5).to_dict(orient="records"),
                )
            )
            report.uniqueness = _pct(n - dup.sum(), n)

    # 4. Consistency — cross-column rules (query string; rows that DON'T match are bad)
    inconsistent = pd.Series(False, index=df.index)
    for cr in consistency_rules or []:
        try:
            match = df.eval(cr.expression)
            bad = ~match.fillna(True)
        except Exception:
            continue
        if bad.any():
            report.issues.append(
                QualityIssue(
                    column=cr.name,
                    rule="consistency",
                    failed_count=int(bad.sum()),
                    severity="MEDIUM",
                    samples=df.loc[bad].head(5).to_dict(orient="records"),
                )
            )
            inconsistent |= bad

    report.consistency = _pct(n - inconsistent.sum(), n)
    bad_mask |= inconsistent

    # 5. Referential integrity — reported here; async resolution in warehouse
    if referential_checks:
        ri_issues = 0
        for column, _schema, _table in referential_checks:
            if column in df.columns and df[column].isna().any():
                ri_issues += int(df[column].isna().sum())
        report.referential_integrity = _pct(n - ri_issues, n)

    # 6. Overall — weighted composite (completeness+validity dominate)
    report.overall_score = round(
        report.completeness * 0.25
        + report.validity * 0.25
        + report.uniqueness * 0.20
        + report.consistency * 0.20
        + report.referential_integrity * 0.10,
        2,
    )
    report.rows_valid = int(n - bad_mask.sum())
    return report


def _clean_nan(obj: Any) -> Any:
    """Recursively replace NaN/Inf values with None for JSON serialization."""
    import math

    if isinstance(obj, dict):
        return {k: _clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_nan(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


async def persist_quality_report(engine: AsyncEngine, report: DataQualityReport) -> int:
    """Persist a DataQualityReport + its issues to the governance schema."""
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                INSERT INTO governance.quality_report (
                    dataset_id, run_id, rows_total, rows_valid,
                    completeness, validity, uniqueness, consistency,
                    referential_integrity, overall_score, generated_at
                ) VALUES (
                    :dataset_id, :run_id, :rows_total, :rows_valid,
                    :completeness, :validity, :uniqueness, :consistency,
                    :ri, :overall, :generated_at
                )
                RETURNING report_id
                """
            ),
            {
                "dataset_id": report.dataset_id,
                "run_id": report.run_id,
                "rows_total": report.rows_total,
                "rows_valid": report.rows_valid,
                "completeness": report.completeness,
                "validity": report.validity,
                "uniqueness": report.uniqueness,
                "consistency": report.consistency,
                "ri": report.referential_integrity,
                "overall": report.overall_score,
                "generated_at": datetime.now(UTC),
            },
        )
        row = result.fetchone()
        if row is None:
            raise RuntimeError("Failed to persist quality report")
        report_id = int(row[0])

        for issue in report.issues:
            await conn.execute(
                text(
                    """
                    INSERT INTO governance.quality_issue (
                        report_id, dataset_id, column_name, rule,
                        failed_count, severity, sample_records
                    ) VALUES (
                        :report_id, :dataset_id, :column, :rule,
                        :failed_count, :severity, CAST(:samples AS jsonb)
                    )
                    """
                ),
                {
                    "report_id": report_id,
                    "dataset_id": report.dataset_id,
                    "column": issue.column,
                    "rule": issue.rule,
                    "failed_count": issue.failed_count,
                    "severity": issue.severity,
                    "samples": json.dumps(_clean_nan(issue.samples)),
                },
            )
    logger.info("quality_report_persisted", dataset=report.dataset_id, report_id=report_id)
    return report_id
