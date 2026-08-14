"""Bronze loader — load validated CSV rows into raw.* (append-only).

Pipeline per 04_DATASET_SPEC.md §14.1:
  read CSV → schema validation → type conversion → row validation →
  deduplication → insert into raw.*
"""

import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.logging import get_logger
from app.warehouse.validator import (
    DATASET_SCHEMAS,
    ValidationResult,
    validate_rows,
    validate_schema,
)

logger = get_logger(__name__)

# raw table per dataset
RAW_TABLE: dict[str, str] = {
    "customer": "raw.raw_customer",
    "usage": "raw.raw_usage",
    "billing": "raw.raw_billing",
    "network": "raw.raw_network",
    "service": "raw.raw_service",
    "campaign": "raw.raw_campaign",
}

# Primary key columns for dedup
DEDUP_KEYS: dict[str, list[str]] = {
    "customer": ["customer_id"],
    "usage": ["customer_id", "usage_date"],
    "billing": ["customer_id", "billing_month"],
    "network": ["customer_id", "measurement_date"],
    "service": ["customer_id", "ticket_date", "complaint_type"],
    "campaign": ["customer_id", "campaign_id", "campaign_date"],
}


def _to_iso_dates(df: pd.DataFrame, date_cols: list[str]) -> pd.DataFrame:
    """Convert date columns to datetime.date objects for insertion."""
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
    return df


# Columns that must be converted to INTEGER before insert
INT_COLUMNS = {
    "customer": ["age"],
    "usage": ["sms_count"],
    "billing": ["overdue_days"],
    "network": [],
    "service": ["ticket_count", "csat_score", "escalation_count"],
    "campaign": [],
}

# Columns that must be converted to FLOAT before insert
FLOAT_COLUMNS = {
    "customer": [],
    "usage": [
        "voice_minutes",
        "data_usage_mb",
        "roaming_usage_mb",
        "peak_usage_mb",
        "international_minutes",
    ],
    "billing": ["monthly_fee", "discount_amount", "package_price"],
    "network": ["latency_ms", "signal_strength", "drop_rate", "packet_loss", "coverage_score"],
    "service": ["waiting_time_min", "resolution_time_min"],
    "campaign": ["campaign_cost"],
}

# Columns that must be converted to BOOLEAN before insert
BOOL_COLUMNS = {
    "campaign": ["coupon_used", "converted"],
}


def _convert_types(df: pd.DataFrame, dataset: str) -> pd.DataFrame:
    """Convert string columns to proper DB types for insertion."""
    out = df.copy()
    for col in INT_COLUMNS.get(dataset, []):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")
    for col in FLOAT_COLUMNS.get(dataset, []):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in BOOL_COLUMNS.get(dataset, []):
        if col in out.columns:
            out[col] = out[col].map({"true": True, "false": False})
    return out


def _rows_for_insert(df: pd.DataFrame) -> list[dict[str, object]]:
    """Convert a DataFrame to insert-ready dict rows (NaN/NA → None)."""
    converted = df.astype(object).where(pd.notna(df), None)
    rows: list[dict[str, object]] = converted.to_dict(orient="records")
    return rows


async def load_bronze(
    engine: AsyncEngine,
    dataset: str,
    file_path: Path,
    batch_id: str,
) -> ValidationResult:
    """Load one dataset CSV into its raw table. Returns validation result."""
    started = time.perf_counter()
    logger.info("etl_bronze_start", dataset=dataset, file=str(file_path), batch_id=batch_id)

    result = ValidationResult(dataset=dataset)

    # 1. Read CSV
    try:
        df = pd.read_csv(file_path, dtype=str, keep_default_na=False)
    except Exception as e:
        logger.error("etl_bronze_read_failed", dataset=dataset, error=str(e))
        raise

    result.rows_total = len(df)

    # 2. Schema validation
    schema_ok, schema_errors = validate_schema(df, dataset)
    if not schema_ok:
        logger.error("etl_bronze_schema_failed", dataset=dataset, errors=schema_errors)
        result.rows_quarantined = result.rows_total
        result.quarantine_reasons["schema_violation"] = result.rows_total
        return result

    # 3. Row validation
    validation = validate_rows(df, dataset)
    result.rows_quarantined += validation.rows_quarantined
    for reason, count in validation.quarantine_reasons.items():
        result.quarantine_reasons[reason] = result.quarantine_reasons.get(reason, 0) + count

    valid_df = df.iloc[list(_accepted_indices(df, dataset))].copy()

    # 4. Deduplication
    dedup_keys = DEDUP_KEYS[dataset]
    before_dedup = len(valid_df)
    valid_df = valid_df.drop_duplicates(subset=dedup_keys, keep="first")
    deduped = before_dedup - len(valid_df)
    if deduped > 0:
        result.quarantine_reasons["duplicate_primary_key"] = (
            result.quarantine_reasons.get("duplicate_primary_key", 0) + deduped
        )
        result.rows_quarantined += deduped

    result.rows_accepted = len(valid_df)

    # 5. Type conversion + insert
    if not valid_df.empty:
        date_cols = [c for c in DATASET_SCHEMAS[dataset] if "date" in c or c == "billing_month"]
        valid_df = _to_iso_dates(valid_df, date_cols)
        valid_df = _convert_types(valid_df, dataset)
        valid_df["import_batch_id"] = batch_id
        valid_df["imported_at"] = datetime.now(UTC)
        valid_df["source_filename"] = file_path.name

        table = RAW_TABLE[dataset]
        cols = list(valid_df.columns)
        values_sql = ", ".join([f":{c}" for c in cols])
        insert_sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({values_sql})"

        rows = _rows_for_insert(valid_df)
        async with engine.begin() as conn:
            # Chunked insert to keep memory bounded on 1M+ rows
            for i in range(0, len(rows), 5000):
                chunk = rows[i : i + 5000]
                await conn.execute(text(insert_sql), chunk)

    elapsed = time.perf_counter() - started
    logger.info(
        "etl_bronze_complete",
        dataset=dataset,
        accepted=result.rows_accepted,
        quarantined=result.rows_quarantined,
        total=result.rows_total,
        duration_sec=round(elapsed, 2),
    )
    return result


def _quarantined_indices(df: pd.DataFrame, dataset: str) -> set[int]:
    """Re-derive quarantined row indices (shared with validator logic)."""
    from app.warehouse.validator import CSAT_RANGE, NUMERIC_RANGES, REQUIRED_COLUMNS, VALID_ENUMS

    bad: set[int] = set()
    for idx in range(len(df)):
        row = df.iloc[idx]
        for col in REQUIRED_COLUMNS[dataset]:
            val = row.get(col)
            if pd.isna(val) or val == "":
                bad.add(idx)
                break
        if idx in bad:
            continue
        for col, valid_vals in VALID_ENUMS.items():
            if col in row.index and pd.notna(row.get(col)) and row.get(col) not in valid_vals:
                bad.add(idx)
                break
        if idx in bad:
            continue
        for col, lo, hi, ds in NUMERIC_RANGES:
            if ds != dataset or col not in row.index:
                continue
            val = row.get(col)
            if pd.notna(val):
                try:
                    fval = float(val)
                except (TypeError, ValueError):
                    bad.add(idx)
                    break
                if fval < lo or fval > hi:
                    bad.add(idx)
                    break
        if idx in bad:
            continue
        if dataset == "service" and pd.notna(row.get("csat_score")) and row.get("csat_score") != "":
            try:
                csat = int(row["csat_score"])
            except (TypeError, ValueError):
                bad.add(idx)
                continue
            if not (CSAT_RANGE[0] <= csat <= CSAT_RANGE[1]):
                bad.add(idx)
                continue
        if (
            dataset == "billing"
            and pd.notna(row.get("discount_amount"))
            and pd.notna(row.get("monthly_fee"))
        ):
            try:
                if float(row["discount_amount"]) > float(row["monthly_fee"]):
                    bad.add(idx)
            except (TypeError, ValueError):
                bad.add(idx)
    return bad


def _accepted_indices(df: pd.DataFrame, dataset: str) -> set[int]:
    """Return the complement of quarantined indices — computed once."""
    bad = _quarantined_indices(df, dataset)
    return set(range(len(df))) - bad
