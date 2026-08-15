"""Analytical Dataset construction — BI-facing analysis wide table.

The terminal step of the phase-1 data science chain:

    Raw → Profiling → Quality → Canonical → Analytical Dataset

Builds a customer-level wide table from the warehouse (dim_customer +
dim_subscription + dim_package + fact_billing + churn status), keyed by
source dataset. Unlike ml/dataset.py (model training features, 32-engineered
columns), this layer is BI-facing: it carries readable business fields
(contract type, payment method, service flags, charges, churn label) that
dashboards, the AI Copilot, and reports consume.

No new schema — the wide table is assembled on read from the Star Schema.
"""

import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.logging import get_logger  # noqa: E402

logger = get_logger(__name__)

# Columns exposed in the analytical wide table (business-readable names)
ANALYTICAL_COLUMNS = [
    "source_customer_id",
    "gender",
    "status",  # active | churned (from churn label)
    "lifecycle_stage",
    "join_date",
    "tenure_months",
    "contract_type",  # Month-to-month | One year | Two year (source value)
    "payment_method",
    "is_paperless_billing",
    "phone_service",
    "multiple_lines",
    "internet_service",
    "online_security",
    "online_backup",
    "device_protection",
    "tech_support",
    "streaming_tv",
    "streaming_movies",
    "monthly_charges",
    "total_charges",
    "is_churn",
]


@dataclass
class AnalyticalDataset:
    """A BI-ready analytical wide table for one source dataset."""

    dataset_id: str
    table: pd.DataFrame
    rows: int
    columns: int
    built_at: str = field(default_factory=lambda: date.today().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "rows": self.rows,
            "columns": self.columns,
            "built_at": self.built_at,
            "column_names": list(self.table.columns),
        }


async def build_analytical_dataset(
    engine: AsyncEngine, dataset_id: str, billing_month: str | None = None
) -> AnalyticalDataset | None:
    """Build the customer-level analytical wide table for a source dataset.

    Args:
        engine: async engine.
        dataset_id: governance.dataset_registry id (e.g. IBM_TELCO_V1).
        billing_month: optional 'YYYY-MM' filter on the billing fact.

    Returns:
        AnalyticalDataset, or None if the dataset has no warehouse rows.
    """
    billing_filter = ""
    params: dict[str, Any] = {"dataset_id": dataset_id}
    if billing_month:
        billing_filter = "AND fb.billing_month = :bm"
        params["bm"] = date(int(billing_month[:4]), int(billing_month[5:7]), 1)

    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                f"""
                SELECT
                    dc.source_customer_id,
                    dc.gender,
                    dc.status,
                    dc.lifecycle_stage,
                    dc.join_date,
                    ds.tenure_months,
                    ds.contract_type,
                    ds.payment_method,
                    ds.is_paperless_billing,
                    ds.phone_service,
                    ds.multiple_lines,
                    ds.internet_service,
                    ds.online_security,
                    ds.online_backup,
                    ds.device_protection,
                    ds.tech_support,
                    ds.streaming_tv,
                    ds.streaming_movies,
                    fb.monthly_fee AS monthly_charges,
                    fb.package_price AS total_charges,
                    CASE WHEN dc.status = 'churned' THEN 1 ELSE 0 END AS is_churn
                FROM warehouse.dim_customer dc
                LEFT JOIN warehouse.dim_subscription ds
                    ON ds.source_customer_id = dc.source_customer_id
                   AND ds.dataset_id = :dataset_id
                LEFT JOIN warehouse.fact_billing fb
                    ON fb.customer_id = dc.customer_id
                WHERE dc.source_customer_id IN (
                    SELECT source_customer_id FROM warehouse.dim_subscription
                    WHERE dataset_id = :dataset_id
                )
                {billing_filter}
                """
            ),
            params,
        )
        rows = result.fetchall()

    if not rows:
        logger.info("analytical_dataset_empty", dataset=dataset_id)
        return None

    df = pd.DataFrame(rows, columns=ANALYTICAL_COLUMNS)
    dataset = AnalyticalDataset(
        dataset_id=dataset_id,
        table=df,
        rows=len(df),
        columns=len(df.columns),
    )
    logger.info(
        "analytical_dataset_built",
        dataset=dataset_id,
        rows=dataset.rows,
        columns=dataset.columns,
    )
    return dataset


if __name__ == "__main__":
    import asyncio

    from app.infrastructure.database.session import engine

    async def main() -> None:
        dataset = await build_analytical_dataset(engine, "IBM_TELCO_V1")
        if dataset is None:
            print("No analytical dataset")
            return
        print(f"Analytical dataset: {dataset.rows:,} rows × {dataset.columns} cols")
        print("\nFirst 5 rows (key columns):")
        cols = [
            "source_customer_id",
            "gender",
            "contract_type",
            "monthly_charges",
            "is_churn",
        ]
        print(dataset.table[cols].head().to_string(index=False))
        print(f"\nChurn rate: {dataset.table['is_churn'].mean():.1%}")
        print(f"Avg monthly charges: ${dataset.table['monthly_charges'].mean():.2f}")
        await engine.dispose()

    asyncio.run(main())
