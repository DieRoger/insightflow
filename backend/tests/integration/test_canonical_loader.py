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


class TestIBMServiceMappingIntegration:
    """E1 regression: IBM Telco service columns must land non-null in the
    warehouse after canonical load (previously all 9 were NULL)."""

    async def test_ibm_service_flags_persist_non_null(self) -> None:
        """Load a fixture canonical dict WITH service data and assert the 9
        service columns are stored with real values (not all NULL)."""
        import pandas as pd

        sid = "IBM_SVC_TEST_001"
        canonical = {
            "customer": pd.DataFrame({"source_customer_id": [sid], "gender": ["Female"]}),
            "subscription": pd.DataFrame(
                {
                    "source_customer_id": [sid],
                    "tenure_months": [6],
                    "contract_type": ["Month-to-month"],
                }
            ),
            "service": pd.DataFrame(
                {
                    "source_customer_id": [sid],
                    "phone_service": [True],
                    "multiple_lines": [True],
                    "internet_service": ["DSL"],
                    "online_security": [False],
                    "online_backup": [True],
                    "device_protection": [False],
                    "tech_support": [True],
                    "streaming_tv": [False],
                    "streaming_movies": [True],
                }
            ),
            "churn": pd.DataFrame({"source_customer_id": [sid], "is_churn": [0]}),
            "billing": pd.DataFrame({"source_customer_id": [sid], "monthly_charges": [45.0]}),
        }

        await load_canonical(engine, canonical, "IBM_TELCO_V1")

        # Verify all 9 service columns are stored, not NULL
        async with engine.connect() as conn:
            r = await conn.execute(
                text(
                    """
                    SELECT phone_service, multiple_lines, internet_service,
                           online_security, online_backup, device_protection,
                           tech_support, streaming_tv, streaming_movies
                    FROM warehouse.dim_subscription
                    WHERE source_customer_id = :sid AND dataset_id = 'IBM_TELCO_V1'
                    """
                ),
                {"sid": sid},
            )
            row = r.fetchone()
            assert row is not None, "subscription row not persisted"
            # 9 service columns — none may be NULL
            assert all(v is not None for v in row), f"NULL service flags: {row}"
            # Spot-check values round-tripped
            assert row[0] is True  # phone_service
            assert row[2] == "DSL"  # internet_service
            assert row[6] is True  # tech_support

        # Cleanup (billing FK → dim_customer)
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "DELETE FROM warehouse.fact_billing WHERE customer_id IN "
                    "(SELECT customer_id FROM warehouse.dim_customer WHERE source_customer_id = :sid)"
                ),
                {"sid": sid},
            )
            await conn.execute(
                text("DELETE FROM warehouse.dim_subscription WHERE source_customer_id = :sid"),
                {"sid": sid},
            )
            await conn.execute(
                text("DELETE FROM warehouse.dim_customer WHERE source_customer_id = :sid"),
                {"sid": sid},
            )

    async def test_ibm_full_roundtrip_service_non_null(self) -> None:
        """End-to-end: real IBM raw CSV → canonical → warehouse; assert the
        9 service flags are populated for a sample customer (not all NULL)."""
        adapter = IBMTelcoAdapter()
        raw = adapter.load_raw(adapter_path())
        canonical = adapter.to_canonical(raw)
        assert "service" in canonical
        svc = canonical["service"]
        assert "phone_service" in svc.columns, "service columns not normalized"

        # Load a bounded subset to keep the test fast (all 7k rows is heavy)
        sample_sids = svc["source_customer_id"].head(50).tolist()
        subset = {
            k: v[v["source_customer_id"].isin(sample_sids)]
            for k, v in canonical.items()
            if not v.empty
        }
        subset["service"] = svc[svc["source_customer_id"].isin(sample_sids)]

        await load_canonical(engine, subset, "IBM_TELCO_V1")

        async with engine.connect() as conn:
            r = await conn.execute(
                text(
                    """
                    SELECT COUNT(*) FILTER (WHERE phone_service IS NOT NULL),
                           COUNT(*) FILTER (WHERE internet_service IS NOT NULL),
                           COUNT(*) FILTER (WHERE tech_support IS NOT NULL)
                    FROM warehouse.dim_subscription
                    WHERE dataset_id = 'IBM_TELCO_V1'
                      AND source_customer_id IN (:s1, :s2, :s3, :s4, :s5)
                    """
                ),
                {
                    "s1": sample_sids[0],
                    "s2": sample_sids[1],
                    "s3": sample_sids[2],
                    "s4": sample_sids[3],
                    "s5": sample_sids[4],
                },
            )
            row = r.fetchone()
            assert row is not None
            phone, internet, tech = row
            assert phone == 5, f"phone_service non-null count: {phone}/5"
            assert internet == 5, f"internet_service non-null count: {internet}/5"
            assert tech == 5, f"tech_support non-null count: {tech}/5"

        # Cleanup
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "DELETE FROM warehouse.fact_billing WHERE customer_id IN "
                    "(SELECT customer_id FROM warehouse.dim_customer WHERE source_customer_id IN "
                    "('" + "','".join(sample_sids) + "'))"
                )
            )
            await conn.execute(
                text(
                    "DELETE FROM warehouse.dim_subscription WHERE source_customer_id IN "
                    "('" + "','".join(sample_sids) + "')"
                )
            )
            await conn.execute(
                text(
                    "DELETE FROM warehouse.dim_customer WHERE source_customer_id IN "
                    "('" + "','".join(sample_sids) + "')"
                )
            )


def adapter_path():
    from pathlib import Path

    raw = Path("data/raw/ibm_telco_v1")
    csvs = sorted(raw.glob("*.csv"))
    if csvs:
        return csvs[0]
    raise FileNotFoundError("IBM Telco raw CSV not downloaded — run ingest_dataset.py first")
