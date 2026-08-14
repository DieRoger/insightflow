"""Dataset construction for churn prediction.

Loads features from feature_store + labels from churn_features, splits
train/val/test, and tracks dataset metadata for reproducibility
(02_ARCHITECTURE.md §6 — every dataset has id, creation time, versions).
"""

import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Feature columns used for churn modeling (exclude ids, labels, metadata)
FEATURE_COLUMNS = [
    "tenure_days",
    "customer_age",
    "contract_duration_months",
    "is_postpaid",
    "is_prepaid",
    "avg_daily_data_mb",
    "avg_daily_voice_min",
    "weekend_usage_ratio",
    "night_usage_ratio",
    "peak_usage_ratio",
    "roaming_ratio",
    "international_ratio",
    "arpu",
    "revenue_trend",
    "discount_ratio",
    "payment_delay_avg",
    "overdue_count",
    "drop_rate_avg",
    "latency_avg_ms",
    "coverage_score_avg",
    "complaint_frequency",
    "network_complaint_ratio",
    "billing_complaint_ratio",
    "avg_resolution_time_min",
    "avg_waiting_time_min",
    "csat_avg",
    "escalation_frequency",
    "promotion_response_rate",
    "days_since_last_complaint",
    "days_since_last_campaign",
    "is_heavy_user",
    "is_premium",
]

LABEL_COLUMN = "is_churn"


@dataclass
class Dataset:
    """A constructed training dataset with metadata."""

    dataset_id: str
    feature_version: str
    X_train: pd.DataFrame
    X_val: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_val: pd.Series
    y_test: pd.Series
    n_samples: int
    churn_rate: float


async def build_churn_dataset(engine: AsyncEngine, test_size: float = 0.2) -> Dataset:
    """Build the churn prediction dataset with train/val/test split."""
    started = time.perf_counter()

    async with engine.connect() as conn:
        # Features from customer_features
        feat_cols = ", ".join(FEATURE_COLUMNS)
        feat_result = await conn.execute(
            text(  # nosec B608: FEATURE_COLUMNS is a code constant
                f"SELECT customer_id, {feat_cols} FROM feature_store.customer_features "
                "WHERE feature_version = 'v1.0.0'"
            )
        )
        feat_rows = feat_result.fetchall()
        feat_cols_all = ["customer_id"] + FEATURE_COLUMNS
        features = pd.DataFrame(feat_rows, columns=feat_cols_all)

        # Labels from churn_features
        label_result = await conn.execute(
            text(
                "SELECT customer_id, is_churn FROM feature_store.churn_features "
                "WHERE feature_version = 'v1.0.0'"
            )
        )
        label_rows = label_result.fetchall()
        labels = pd.DataFrame(label_rows, columns=["customer_id", "is_churn"])

    df = features.merge(labels, on="customer_id", how="inner")
    df = df.dropna(subset=FEATURE_COLUMNS).fillna(0)

    # Deterministic split (fixed seed for reproducibility)
    from sklearn.model_selection import train_test_split

    X = df[FEATURE_COLUMNS]
    y = df[LABEL_COLUMN].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42, stratify=y
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_train, y_train, test_size=test_size, random_state=42, stratify=y_train
    )

    dataset = Dataset(
        dataset_id=f"ds_churn_{time.strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}",
        feature_version="v1.0.0",
        X_train=X_train,
        X_val=X_val,
        X_test=X_test,
        y_train=y_train,
        y_val=y_val,
        y_test=y_test,
        n_samples=len(df),
        churn_rate=float(y.mean()),
    )
    logger_info(dataset, started)
    return dataset


def logger_info(dataset: Dataset, started: float) -> None:
    from app.core.logging import get_logger

    get_logger().info(
        "dataset_constructed",
        dataset_id=dataset.dataset_id,
        samples=dataset.n_samples,
        churn_rate=round(dataset.churn_rate, 4),
        train=len(dataset.X_train),
        val=len(dataset.X_val),
        test=len(dataset.X_test),
        duration_sec=round(time.perf_counter() - started, 2),
    )


if __name__ == "__main__":
    import asyncio

    from app.infrastructure.database.session import engine

    async def main() -> None:
        dataset = await build_churn_dataset(engine)
        print(
            f"dataset {dataset.dataset_id}: {dataset.n_samples} samples, "
            f"churn_rate={dataset.churn_rate:.3f}, "
            f"train={len(dataset.X_train)} val={len(dataset.X_val)} test={len(dataset.X_test)}"
        )
        await engine.dispose()

    asyncio.run(main())
