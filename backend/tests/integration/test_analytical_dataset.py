"""Integration tests for the analytical dataset builder (real IBM data)."""

import pytest

from app.infrastructure.database.session import engine
from app.warehouse.analytical import ANALYTICAL_COLUMNS, AnalyticalDataset, build_analytical_dataset

pytestmark = pytest.mark.integration


class TestAnalyticalDatasetBuilder:
    async def test_build_ibm_analytical_dataset(self) -> None:
        """Real IBM data yields a customer-level analytical wide table."""
        dataset = await build_analytical_dataset(engine, "IBM_TELCO_V1")
        assert dataset is not None
        assert isinstance(dataset, AnalyticalDataset)
        assert dataset.rows > 5000
        assert dataset.columns == len(ANALYTICAL_COLUMNS)
        assert list(dataset.table.columns) == ANALYTICAL_COLUMNS

        # Churn label derived from status
        assert set(dataset.table["is_churn"].unique()) <= {0, 1}
        churn_rate = dataset.table["is_churn"].mean()
        assert 0.20 <= churn_rate <= 0.30  # IBM known ~26.5%

        # Business-readable fields present and populated
        assert dataset.table["contract_type"].notna().any()
        assert dataset.table["monthly_charges"].notna().all()

    async def test_build_unknown_dataset_returns_none(self) -> None:
        dataset = await build_analytical_dataset(engine, "DOES_NOT_EXIST_V1")
        assert dataset is None

    async def test_billing_month_filter(self) -> None:
        """Filtering by billing month narrows the wide table."""
        dataset = await build_analytical_dataset(engine, "IBM_TELCO_V1", billing_month="2026-08")
        assert dataset is not None
        assert dataset.rows > 0


class TestAnalyticalDatasetModel:
    def test_to_dict(self) -> None:
        import pandas as pd

        ds = AnalyticalDataset(
            dataset_id="X",
            table=pd.DataFrame({"a": [1]}),
            rows=1,
            columns=1,
        )
        d = ds.to_dict()
        assert d["dataset_id"] == "X"
        assert d["column_names"] == ["a"]
