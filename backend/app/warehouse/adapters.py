"""Source Adapter framework — map any source dataset into the Canonical Schema.

Per the data plan §2: never UNION raw datasets. Each source goes through:

    Source Dataset → Source Adapter → Canonical Schema → Dataset-specific validation

Each adapter declares its registry entry, its canonical mapping, and the
quality rules that gate whether its data may be loaded.
"""

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@dataclass
class RegistryEntry:
    """Metadata written to governance.dataset_registry."""

    dataset_id: str
    dataset_name: str
    source: str
    source_url: str | None = None
    version: str = "v1"
    description: str = ""
    schema_version: str = "canonical_v1"
    source_type: str = "kaggle"
    license: str = ""


@dataclass
class CanonicalMapping:
    """A single source column → canonical column mapping."""

    source_column: str
    canonical_table: str
    canonical_column: str
    transform: str = "direct"  # 'direct' | 'lower' | 'to_numeric' | 'date' | custom lambda name


class SourceAdapter(ABC):
    """Base class for all dataset adapters."""

    registry_entry: RegistryEntry

    @abstractmethod
    def load_raw(self, path: Path) -> pd.DataFrame:
        """Load the raw source file into a DataFrame."""

    @abstractmethod
    def to_canonical(self, df: pd.DataFrame) -> dict[str, pd.DataFrame]:
        """Transform raw rows into canonical tables.

        Returns { canonical_table_name: DataFrame } — e.g.
        {"customer": ..., "subscription": ..., "churn": ...}
        """

    @abstractmethod
    def quality_column_rules(self) -> list[Any]:
        """Return the ColumnRule list for quality gating."""

    def quality_consistency_rules(self) -> list[Any]:
        """Return cross-column consistency rules (default none)."""
        return []

    def unique_keys(self) -> list[str] | None:
        """Primary key columns for uniqueness checks."""
        return None


# ---------------------------------------------------------------------------
# IBM Telco adapter (blastchar/telco-customer-churn)
# ---------------------------------------------------------------------------

# IBM Telco source columns
IBM_TELCO_COLUMNS = [
    "customerID",
    "gender",
    "SeniorCitizen",
    "Partner",
    "Dependents",
    "tenure",
    "PhoneService",
    "MultipleLines",
    "InternetService",
    "OnlineSecurity",
    "OnlineBackup",
    "DeviceProtection",
    "TechSupport",
    "StreamingTV",
    "StreamingMovies",
    "Contract",
    "PaperlessBilling",
    "PaymentMethod",
    "MonthlyCharges",
    "TotalCharges",
    "Churn",
]

# Source → Canonical mapping for the subscription service flags.
# The canonical schema (dim_subscription) uses snake_case columns; the source
# dataset uses CamelCase. Normalization happens at the adapter boundary so the
# canonical loader never sees source-specific column names.
SERVICE_MAPPING: dict[str, str] = {
    "PhoneService": "phone_service",
    "MultipleLines": "multiple_lines",
    "InternetService": "internet_service",
    "OnlineSecurity": "online_security",
    "OnlineBackup": "online_backup",
    "DeviceProtection": "device_protection",
    "TechSupport": "tech_support",
    "StreamingTV": "streaming_tv",
    "StreamingMovies": "streaming_movies",
}


class IBMTelcoAdapter(SourceAdapter):
    """Adapter for the IBM Telco Customer Churn dataset (Kaggle)."""

    registry_entry = RegistryEntry(
        dataset_id="IBM_TELCO_V1",
        dataset_name="IBM Telco Customer Churn",
        source="kaggle",
        source_url="https://www.kaggle.com/datasets/blastchar/telco-customer-churn",
        version="v1",
        description="IBM sample telco dataset: 7043 customers with churn labels",
        source_type="kaggle",
        license="CC0: Public Domain",
    )

    def load_raw(self, path: Path) -> pd.DataFrame:
        df = pd.read_csv(path)
        # IBM known data issue: TotalCharges has blank strings → coerce
        df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
        return df

    def to_canonical(self, df: pd.DataFrame) -> dict[str, pd.DataFrame]:
        canonical: dict[str, pd.DataFrame] = {}

        # customer: identity + demographics
        canonical["customer"] = df.rename(
            columns={
                "customerID": "source_customer_id",
                "gender": "gender",
                "SeniorCitizen": "is_senior",
                "Partner": "has_partner",
                "Dependents": "has_dependents",
            }
        )[
            [
                "source_customer_id",
                "gender",
                "is_senior",
                "has_partner",
                "has_dependents",
            ]
        ].copy()

        # subscription: contract + payment terms
        canonical["subscription"] = df.rename(
            columns={
                "customerID": "source_customer_id",
                "tenure": "tenure_months",
                "Contract": "contract_type",
                "PaperlessBilling": "is_paperless_billing",
                "PaymentMethod": "payment_method",
            }
        )[
            [
                "source_customer_id",
                "tenure_months",
                "contract_type",
                "is_paperless_billing",
                "payment_method",
            ]
        ].copy()

        # service: subscribed services (one-hot → canonical boolean columns).
        # Normalize CamelCase source columns to canonical snake_case at the
        # adapter boundary so the loader consumes canonical names only.
        service_cols = list(SERVICE_MAPPING.values())
        canonical["service"] = (
            df.rename(columns={"customerID": "source_customer_id"})
            .rename(columns=SERVICE_MAPPING)[["source_customer_id"] + service_cols]
            .copy()
        )

        # billing: charges
        canonical["billing"] = df.rename(
            columns={
                "customerID": "source_customer_id",
                "MonthlyCharges": "monthly_charges",
                "TotalCharges": "total_charges",
            }
        )[["source_customer_id", "monthly_charges", "total_charges"]].copy()

        # churn: label
        canonical["churn"] = df.rename(
            columns={"customerID": "source_customer_id", "Churn": "is_churn"}
        )[["source_customer_id", "is_churn"]].copy()
        canonical["churn"]["is_churn"] = canonical["churn"]["is_churn"].map({"Yes": 1, "No": 0})

        return canonical

    def quality_column_rules(self) -> list[Any]:
        from app.warehouse.quality import ColumnRule

        return [
            ColumnRule("customerID", "required"),
            ColumnRule("gender", "enum", ["Male", "Female"]),
            ColumnRule("tenure", "non_negative"),
            ColumnRule("MonthlyCharges", "non_negative"),
            ColumnRule("TotalCharges", "non_negative"),
            ColumnRule("Churn", "enum", ["Yes", "No"]),
        ]

    def quality_consistency_rules(self) -> list[Any]:
        from app.warehouse.quality import ConsistencyRule

        return [
            ConsistencyRule(
                name="total_gte_monthly",
                expression="TotalCharges >= MonthlyCharges",
                description="Total charges must be at least monthly charges",
            ),
            ConsistencyRule(
                name="tenure_zero_implies_no_charges",
                expression="(tenure > 0) | (TotalCharges == 0)",
                description="Zero tenure should imply zero total charges",
            ),
        ]

    def unique_keys(self) -> list[str]:
        return ["customerID"]
