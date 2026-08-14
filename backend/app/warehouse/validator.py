"""ETL data validation — schema and row-level quality rules.

Implements the validation contract from 04_DATASET_SPEC.md §11.
"""

from dataclasses import dataclass, field

import pandas as pd

# Dataset → expected column set (04_DATASET_SPEC.md §4–§9)
DATASET_SCHEMAS: dict[str, set[str]] = {
    "customer": {
        "customer_id",
        "gender",
        "age",
        "city",
        "province",
        "join_date",
        "contract_type",
        "package_id",
        "package_name",
        "status",
    },
    "usage": {
        "customer_id",
        "usage_date",
        "voice_minutes",
        "sms_count",
        "data_usage_mb",
        "roaming_usage_mb",
        "peak_usage_mb",
        "international_minutes",
    },
    "billing": {
        "customer_id",
        "billing_month",
        "monthly_fee",
        "discount_amount",
        "payment_status",
        "overdue_days",
        "package_price",
        "payment_method",
    },
    "network": {
        "customer_id",
        "measurement_date",
        "latency_ms",
        "signal_strength",
        "drop_rate",
        "packet_loss",
        "coverage_score",
    },
    "service": {
        "customer_id",
        "ticket_date",
        "ticket_count",
        "complaint_type",
        "waiting_time_min",
        "resolution_time_min",
        "csat_score",
        "escalation_count",
    },
    "campaign": {
        "customer_id",
        "campaign_id",
        "campaign_date",
        "promotion_type",
        "coupon_used",
        "converted",
        "channel",
        "campaign_cost",
    },
}

VALID_ENUMS = {
    "contract_type": {"prepaid", "postpaid", "hybrid"},
    "status": {"active", "suspended", "churned"},
    "payment_status": {"paid", "overdue", "pending"},
    "complaint_type": {"billing", "network", "service", "other"},
    "promotion_type": {"discount", "bundle_upgrade", "free_trial", "loyalty_reward"},
    "channel": {"sms", "email", "app_push", "call_center"},
}

REQUIRED_COLUMNS = {
    "customer": {"customer_id", "join_date", "contract_type", "package_id", "status"},
    "usage": {"customer_id", "usage_date"},
    "billing": {"customer_id", "billing_month", "monthly_fee", "payment_status", "package_price"},
    "network": {"customer_id", "measurement_date"},
    "service": {"customer_id", "ticket_date", "ticket_count"},
    "campaign": {"customer_id", "campaign_id", "campaign_date"},
}

# Numeric range rules: (column, min, max, dataset)
NUMERIC_RANGES: list[tuple[str, float, float, str]] = [
    ("age", 0, 120, "customer"),
    ("voice_minutes", 0, 10000, "usage"),
    ("sms_count", 0, 10000, "usage"),
    ("data_usage_mb", 0, 100000, "usage"),
    ("roaming_usage_mb", 0, 100000, "usage"),
    ("peak_usage_mb", 0, 100000, "usage"),
    ("international_minutes", 0, 10000, "usage"),
    ("monthly_fee", 0, 100000, "billing"),
    ("discount_amount", 0, 100000, "billing"),
    ("overdue_days", 0, 10000, "billing"),
    ("package_price", 0, 100000, "billing"),
    ("latency_ms", 0, 10000, "network"),
    ("signal_strength", 0, 100, "network"),
    ("drop_rate", 0, 1, "network"),
    ("packet_loss", 0, 1, "network"),
    ("coverage_score", 0, 100, "network"),
    ("ticket_count", 0, 10000, "service"),
    ("waiting_time_min", 0, 100000, "service"),
    ("resolution_time_min", 0, 100000, "service"),
    ("escalation_count", 0, 1000, "service"),
    ("campaign_cost", 0, 100000, "campaign"),
]

CSAT_RANGE = (1, 5)


@dataclass
class ValidationResult:
    """Outcome of validating one dataset file."""

    dataset: str
    rows_total: int = 0
    rows_accepted: int = 0
    rows_quarantined: int = 0
    quarantine_reasons: dict[str, int] = field(default_factory=dict)
    warnings: int = 0


def validate_schema(df: pd.DataFrame, dataset: str) -> tuple[bool, list[str]]:
    """Check that required columns exist and are correctly typed."""
    errors: list[str] = []
    expected = DATASET_SCHEMAS[dataset]
    missing = expected - set(df.columns)
    if missing:
        errors.append(f"Missing columns: {sorted(missing)}")

    required_missing = REQUIRED_COLUMNS[dataset] - set(df.columns)
    if required_missing:
        errors.append(f"Missing required columns: {sorted(required_missing)}")

    return (len(errors) == 0, errors)


def _check_row(df: pd.DataFrame, idx: int, dataset: str) -> tuple[bool, str | None]:
    """Validate a single row against quality rules. Returns (valid, reason)."""
    row = df.iloc[idx]

    # Required column non-null
    for col in REQUIRED_COLUMNS[dataset]:
        val = row.get(col)
        if pd.isna(val) or val == "":
            return False, f"missing_required:{col}"

    # Enum values
    for col, valid_vals in VALID_ENUMS.items():
        if col in row.index and pd.notna(row.get(col)) and row.get(col) not in valid_vals:
            return False, f"invalid_enum:{col}"

    # Numeric ranges
    for col, lo, hi, ds in NUMERIC_RANGES:
        if ds != dataset or col not in row.index:
            continue
        val = row.get(col)
        if pd.notna(val):
            try:
                fval = float(val)
            except (TypeError, ValueError):
                return False, f"not_numeric:{col}"
            if fval < lo or fval > hi:
                return False, f"out_of_range:{col}"

    # CSAT range
    if dataset == "service" and pd.notna(row.get("csat_score")) and row.get("csat_score") != "":
        try:
            csat = int(row["csat_score"])
        except (TypeError, ValueError):
            return False, "not_numeric:csat_score"
        if not (CSAT_RANGE[0] <= csat <= CSAT_RANGE[1]):
            return False, "out_of_range:csat_score"

    if (
        dataset == "billing"
        and pd.notna(row.get("discount_amount"))
        and pd.notna(row.get("monthly_fee"))
    ):
        try:
            if float(row["discount_amount"]) > float(row["monthly_fee"]):
                return False, "business_rule:discount_exceeds_fee"
        except (TypeError, ValueError):
            return False, "not_numeric:discount_amount"

    return True, None


def validate_rows(df: pd.DataFrame, dataset: str) -> ValidationResult:
    """Validate all rows, separating valid from quarantined."""
    result = ValidationResult(dataset=dataset, rows_total=len(df))
    valid_idx: list[int] = []

    for idx in range(len(df)):
        valid, reason = _check_row(df, idx, dataset)
        if valid:
            valid_idx.append(idx)
        else:
            result.rows_quarantined += 1
            assert reason is not None
            result.quarantine_reasons[reason] = result.quarantine_reasons.get(reason, 0) + 1

    result.rows_accepted = len(valid_idx)
    return result
