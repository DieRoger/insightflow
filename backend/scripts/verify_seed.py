"""Verify seeded reference data counts."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.infrastructure.database.session import engine  # noqa: E402


async def main() -> None:
    async with engine.connect() as conn:
        checks = [
            ("dim_time rows", "SELECT COUNT(*) FROM warehouse.dim_time"),
            ("metric_registry rows", "SELECT COUNT(*) FROM semantic.metric_registry"),
            ("feature_registry rows", "SELECT COUNT(*) FROM feature_store.feature_registry"),
            (
                "metric categories",
                "SELECT category, COUNT(*) FROM semantic.metric_registry GROUP BY category ORDER BY category",
            ),
        ]
        for label, sql in checks:
            result = await conn.execute(text(sql))
            rows = result.fetchall()
            print(f"{label}: {rows}")

        # sample dim_time row
        r = await conn.execute(
            text(
                "SELECT date_id, full_date, year, quarter, is_weekend FROM warehouse.dim_time WHERE full_date = '2026-08-15'"
            )
        )
        print("dim_time sample 2026-08-15:", r.fetchall())

        # sample metric
        r = await conn.execute(
            text(
                "SELECT metric_name, category, unit FROM semantic.metric_registry WHERE metric_name='arpu'"
            )
        )
        print("arpu metric:", r.fetchall())

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
