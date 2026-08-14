"""Verify Silver layer and semantic views after ETL."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.infrastructure.database.session import engine  # noqa: E402


async def main() -> None:
    async with engine.connect() as conn:
        checks = [
            ("dim_customer", "SELECT COUNT(*) FROM warehouse.dim_customer"),
            ("dim_package", "SELECT COUNT(*) FROM warehouse.dim_package"),
            ("dim_region", "SELECT COUNT(*) FROM warehouse.dim_region"),
            ("fact_usage_daily", "SELECT COUNT(*) FROM warehouse.fact_usage_daily"),
            ("fact_billing", "SELECT COUNT(*) FROM warehouse.fact_billing"),
            ("fact_network", "SELECT COUNT(*) FROM warehouse.fact_network"),
            ("fact_service", "SELECT COUNT(*) FROM warehouse.fact_service"),
            ("fact_campaign", "SELECT COUNT(*) FROM warehouse.fact_campaign"),
            ("kpi_arpu", "SELECT COUNT(*) FROM semantic.kpi_arpu"),
            ("kpi_revenue", "SELECT COUNT(*) FROM semantic.kpi_revenue"),
        ]
        for label, sql in checks:
            r = await conn.execute(text(sql))
            print(f"{label}: {r.scalar()}")

        # ARPU sample
        r = await conn.execute(
            text(
                "SELECT region_name, COUNT(*) FROM semantic.kpi_arpu GROUP BY region_name ORDER BY region_name"
            )
        )
        print("\nkpi_arpu by region:", r.fetchall())

        # ARPU value sanity
        r = await conn.execute(
            text("SELECT AVG(arpu), MIN(arpu), MAX(arpu) FROM semantic.kpi_arpu")
        )
        print("arpu stats (avg/min/max):", r.fetchall())
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
