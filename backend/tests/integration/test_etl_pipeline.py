"""Integration tests for ETL bronze + silver loaders against a real test database.

These tests run against the local PostgreSQL (matching DATABASE_URL). They
verify the full ETL chain: CSV → raw.* → warehouse.* (Star Schema).
"""

import asyncio
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import text

from app.infrastructure.database.session import engine
from app.warehouse.bronze_loader import (
    _accepted_indices,
    _convert_types,
    _rows_for_insert,
    _to_iso_dates,
)

pytestmark = pytest.mark.integration


class TestBronzeHelpers:
    def test_to_iso_dates_converts_to_date_objects(self) -> None:
        """Date columns become datetime.date objects (asyncpg-compatible)."""
        df = pd.DataFrame({"join_date": ["2024-04-10", "2025-01-01"]})
        df = _to_iso_dates(df, ["join_date"])
        assert str(df["join_date"].iloc[0]) == "2024-04-10"
        assert str(df["join_date"].iloc[1]) == "2025-01-01"

    def test_convert_types_numeric_and_bool(self) -> None:
        """Numeric columns convert to numbers; booleans to True/False."""
        df = pd.DataFrame(
            {
                "age": ["32", ""],
                "voice_minutes": ["52.5", ""],
                "coupon_used": ["true", "false"],
                "converted": ["false", "true"],
            }
        )
        df = _convert_types(df, "usage")
        # age is only converted for customer dataset
        assert pd.isna(df["voice_minutes"].iloc[0]) is False
        assert df["voice_minutes"].iloc[0] == 52.5

        camp = pd.DataFrame({"coupon_used": ["true", "false"], "converted": ["false", "true"]})
        camp = _convert_types(camp, "campaign")
        assert bool(camp["coupon_used"].iloc[0]) is True
        assert bool(camp["coupon_used"].iloc[1]) is False

    def test_rows_for_insert_replaces_nan_with_none(self) -> None:
        """NaN/NA values become None for asyncpg parameter binding."""
        df = pd.DataFrame({"a": [1.0, float("nan")], "b": ["x", ""]})
        rows = _rows_for_insert(df)
        assert rows[0]["a"] == 1.0
        assert rows[1]["a"] is None
        assert rows[1]["b"] == ""

    def test_accepted_indices_matches_quarantine(self) -> None:
        """Accepted indices are exactly the complement of quarantined."""
        df = pd.DataFrame(
            {
                "customer_id": ["CUST-1", "CUST-2", "CUST-3"],
                "join_date": ["2024-01-01", "2024-01-02", "2024-01-03"],
                "contract_type": ["postpaid", "prepaid", "bad_type"],
                "package_id": ["PKG-1", "PKG-2", "PKG-3"],
                "status": ["active", "active", "active"],
            }
        )
        accepted = _accepted_indices(df, "customer")
        assert accepted == {0, 1}


@pytest.mark.asyncio
async def test_full_etl_chain_end_to_end(tmp_path: Path) -> None:
    """CSV → raw → warehouse full chain works against real PostgreSQL.

    Uses a temporary CSV and a unique test batch so it never disturbs
    pre-loaded data used by other integration tests.
    """
    # Minimal valid customer CSV in a temporary dir (sync file IO in a thread)
    customer_csv = tmp_path / "customer_test.csv"
    await asyncio.to_thread(
        customer_csv.write_text,
        "customer_id,gender,age,city,province,join_date,contract_type,package_id,package_name,status\n"
        "CUST-90001,Male,34,Shanghai,Shanghai,2024-04-10,postpaid,PKG-PREM-1,Premium,active\n"
        "CUST-90002,Female,28,Beijing,Beijing,2025-01-15,prepaid,PKG-DATA-1,Data,active\n",
        encoding="utf-8",
    )

    # Bronze load
    from app.warehouse.bronze_loader import load_bronze

    result = await load_bronze(engine, "customer", customer_csv, "it_test_batch")
    assert result.rows_accepted == 2

    # Verify raw: test customers present (other data may coexist)
    async with engine.connect() as conn:
        r = await conn.execute(
            text("SELECT COUNT(*) FROM raw.raw_customer WHERE import_batch_id = 'it_test_batch'")
        )
        assert r.scalar() == 2

    # Silver load
    from app.warehouse.silver_loader import load_dimensions, load_facts

    await load_dimensions(engine)
    await load_facts(engine)

    async with engine.connect() as conn:
        r = await conn.execute(
            text(
                "SELECT COUNT(*) FROM warehouse.dim_customer "
                "WHERE source_customer_id IN ('CUST-90001', 'CUST-90002')"
            )
        )
        assert r.scalar() == 2
        r = await conn.execute(text("SELECT COUNT(*) FROM warehouse.dim_package"))
        assert r.scalar() >= 2
        r = await conn.execute(text("SELECT COUNT(*) FROM warehouse.dim_region"))
        assert r.scalar() >= 2

    # Clean up only the test batch rows (leave other test data intact).
    # Order matters: delete fact rows (FK to dim_customer) before dim_customer.
    test_ids = ("CUST-90001", "CUST-90002")
    async with engine.begin() as conn:
        # Facts referencing test customers
        for table in (
            "warehouse.fact_campaign",
            "warehouse.fact_service",
            "warehouse.fact_network",
            "warehouse.fact_billing",
            "warehouse.fact_usage_daily",
        ):
            await conn.execute(
                text(
                    f"DELETE FROM {table} WHERE customer_id IN "
                    "(SELECT customer_id FROM warehouse.dim_customer "
                    f"WHERE source_customer_id IN {test_ids})"
                )
            )
        # Raw rows from the test batch
        for table in (
            "raw.raw_customer",
            "raw.raw_usage",
            "raw.raw_billing",
            "raw.raw_network",
            "raw.raw_service",
            "raw.raw_campaign",
        ):
            await conn.execute(text(f"DELETE FROM {table} WHERE import_batch_id = 'it_test_batch'"))
        # Dim rows for test customers
        for sid in test_ids:
            await conn.execute(
                text("DELETE FROM warehouse.dim_customer WHERE source_customer_id = :sid"),
                {"sid": sid},
            )
