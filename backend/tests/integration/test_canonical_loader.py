"""Integration tests for the canonical loader (adapter output → warehouse)."""

import pytest
from sqlalchemy import text

from app.infrastructure.database.session import engine
from app.warehouse.adapters import IBMTelcoAdapter
from app.warehouse.canonical_loader import _bool_map, load_canonical

pytestmark = pytest.mark.integration

TEST_SOURCE_ID = "canonical_test_cust"


class TestCanonicalLoader:
    async def test_load_canonical_populates_warehouse(self) -> None:
        """A minimal canonical dict lands in dim_customer + dim_subscription."""
        import pandas as pd

        canonical = {
            "customer": pd.DataFrame(
                {"source_customer_id": [TEST_SOURCE_ID], "gender": ["Female"]}
            ),
            "subscription": pd.DataFrame(
                {
                    "source_customer_id": [TEST_SOURCE_ID],
                    "tenure_months": [12],
                    "contract_type": ["Month-to-month"],
                    "is_paperless_billing": [True],
                    "payment_method": ["Electronic check"],
                }
            ),
            "churn": pd.DataFrame({"source_customer_id": [TEST_SOURCE_ID], "is_churn": [0]}),
            "billing": pd.DataFrame(
                {"source_customer_id": [TEST_SOURCE_ID], "monthly_charges": [49.5]}
            ),
        }

        counts = await load_canonical(engine, canonical, "TEST_CANONICAL_V1")
        assert counts["customer"] == 1
        assert counts["subscription"] == 1

        async with engine.connect() as conn:
            r = await conn.execute(
                text(
                    "SELECT status, gender, contract_type FROM warehouse.dim_customer "
                    "WHERE source_customer_id = :sid"
                ),
                {"sid": TEST_SOURCE_ID},
            )
            row = r.fetchone()
            assert row is not None
            assert row[0] == "active"  # is_churn=0 → active
            assert row[1] == "Female"
            assert row[2] == "Month-to-month"

            r = await conn.execute(
                text(
                    "SELECT tenure_months, contract_type FROM warehouse.dim_subscription "
                    "WHERE source_customer_id = :sid AND dataset_id = 'TEST_CANONICAL_V1'"
                ),
                {"sid": TEST_SOURCE_ID},
            )
            row = r.fetchone()
            assert row is not None
            assert row[0] == 12

        # Cleanup (order matters: billing FK → dim_customer)
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "DELETE FROM warehouse.fact_billing WHERE customer_id IN "
                    "(SELECT customer_id FROM warehouse.dim_customer WHERE source_customer_id = :sid)"
                ),
                {"sid": TEST_SOURCE_ID},
            )
            await conn.execute(
                text("DELETE FROM warehouse.dim_subscription WHERE source_customer_id = :sid"),
                {"sid": TEST_SOURCE_ID},
            )
            await conn.execute(
                text("DELETE FROM warehouse.dim_customer WHERE source_customer_id = :sid"),
                {"sid": TEST_SOURCE_ID},
            )

    async def test_churned_customer_gets_churned_status(self) -> None:
        """is_churn=1 maps to status='churned'."""
        import pandas as pd

        canonical = {
            "customer": pd.DataFrame({"source_customer_id": [TEST_SOURCE_ID]}),
            "subscription": pd.DataFrame(
                {
                    "source_customer_id": [TEST_SOURCE_ID],
                    "tenure_months": [3],
                    "contract_type": ["One year"],
                }
            ),
            "churn": pd.DataFrame({"source_customer_id": [TEST_SOURCE_ID], "is_churn": [1]}),
            "billing": pd.DataFrame(
                {"source_customer_id": [TEST_SOURCE_ID], "monthly_charges": [30.0]}
            ),
        }

        await load_canonical(engine, canonical, "TEST_CANONICAL_V1")
        async with engine.connect() as conn:
            r = await conn.execute(
                text(
                    "SELECT status, lifecycle_stage FROM warehouse.dim_customer "
                    "WHERE source_customer_id = :sid"
                ),
                {"sid": TEST_SOURCE_ID},
            )
            row = r.fetchone()
            assert row[0] == "churned"
            assert row[1] == "churned"

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "DELETE FROM warehouse.fact_billing WHERE customer_id IN "
                    "(SELECT customer_id FROM warehouse.dim_customer WHERE source_customer_id = :sid)"
                ),
                {"sid": TEST_SOURCE_ID},
            )
            await conn.execute(
                text("DELETE FROM warehouse.dim_subscription WHERE source_customer_id = :sid"),
                {"sid": TEST_SOURCE_ID},
            )
            await conn.execute(
                text("DELETE FROM warehouse.dim_customer WHERE source_customer_id = :sid"),
                {"sid": TEST_SOURCE_ID},
            )


class TestBoolMap:
    def test_yes_no_mapping(self) -> None:
        import pandas as pd

        result = _bool_map(pd.Series(["Yes", "No", "Yes"]))
        assert result.tolist() == [True, False, True]

    def test_boolean_identity(self) -> None:
        import pandas as pd

        result = _bool_map(pd.Series([True, False]))
        assert result.tolist() == [True, False]


class TestIBMAdapterRoundTrip:
    def test_adapter_canonical_keys(self) -> None:
        adapter = IBMTelcoAdapter()
        assert set(adapter.to_canonical(adapter.load_raw(adapter_path()))) == {
            "customer",
            "subscription",
            "service",
            "billing",
            "churn",
        }


def adapter_path():
    from pathlib import Path

    raw = Path("data/raw/ibm_telco_v1")
    csvs = sorted(raw.glob("*.csv"))
    if csvs:
        return csvs[0]
    raise FileNotFoundError("IBM Telco raw CSV not downloaded — run ingest_dataset.py first")
