"""Verify IBM Telco data landed in the warehouse and is queryable."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.infrastructure.database.session import engine  # noqa: E402


async def main() -> None:
    async with engine.connect() as conn:
        checks = [
            (
                "dim_customer (IBM)",
                "SELECT COUNT(*) FROM warehouse.dim_customer WHERE source_customer_id LIKE '____-_____'",
            ),
            (
                "dim_customer status",
                "SELECT status, COUNT(*) FROM warehouse.dim_customer WHERE source_customer_id LIKE '____-_____' GROUP BY status",
            ),
            (
                "dim_subscription",
                "SELECT COUNT(*) FROM warehouse.dim_subscription WHERE dataset_id='IBM_TELCO_V1'",
            ),
            (
                "dim_subscription contract",
                "SELECT contract_type, COUNT(*) FROM warehouse.dim_subscription WHERE dataset_id='IBM_TELCO_V1' GROUP BY contract_type",
            ),
            (
                "fact_billing (IBM)",
                "SELECT COUNT(*), AVG(monthly_fee), MAX(billing_month) FROM warehouse.fact_billing fb JOIN warehouse.dim_customer dc ON fb.customer_id=dc.customer_id WHERE dc.source_customer_id LIKE '____-_____'",
            ),
        ]
        for label, sql in checks:
            r = await conn.execute(text(sql))
            print(f"{label}: {r.fetchall()}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
