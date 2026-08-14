"""Reset raw and warehouse tables for a clean ETL run."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.infrastructure.database.session import engine  # noqa: E402

TABLES = [
    "warehouse.fact_campaign",
    "warehouse.fact_service",
    "warehouse.fact_network",
    "warehouse.fact_billing",
    "warehouse.fact_usage_daily",
    "warehouse.dim_customer",
    "warehouse.dim_package",
    "warehouse.dim_region",
    "raw.raw_campaign",
    "raw.raw_service",
    "raw.raw_network",
    "raw.raw_billing",
    "raw.raw_usage",
    "raw.raw_customer",
]


async def main() -> None:
    async with engine.begin() as conn:
        for table in TABLES:
            await conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
    print("Reset complete:", ", ".join(TABLES))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
