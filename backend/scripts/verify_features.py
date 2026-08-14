"""Verify feature store contents and label balance."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.infrastructure.database.session import engine  # noqa: E402


async def main() -> None:
    async with engine.connect() as conn:
        r = await conn.execute(
            text("SELECT COUNT(*), COUNT(arpu), AVG(arpu) FROM feature_store.customer_features")
        )
        print("customer_features (total/with_arpu/avg_arpu):", r.fetchall())

        r = await conn.execute(
            text("SELECT is_churn, COUNT(*) FROM feature_store.churn_features GROUP BY is_churn")
        )
        print("churn label distribution:", r.fetchall())

        r = await conn.execute(
            text(
                "SELECT COUNT(*) FROM feature_store.customer_features "
                "WHERE avg_daily_data_mb > 0 AND arpu > 0"
            )
        )
        print("customers with usage+revenue features:", r.scalar())

        r = await conn.execute(
            text(
                "SELECT feature_version, COUNT(*) FROM feature_store.customer_features "
                "GROUP BY feature_version"
            )
        )
        print("versions:", r.fetchall())
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
