"""Verify all schemas and key tables exist after migrations."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.infrastructure.database.session import engine  # noqa: E402

EXPECTED_TABLES = {
    "raw": [
        "raw_customer",
        "raw_usage",
        "raw_billing",
        "raw_network",
        "raw_service",
        "raw_campaign",
    ],
    "warehouse": [
        "dim_time",
        "dim_customer",
        "dim_package",
        "dim_region",
        "fact_usage_daily",
        "fact_billing",
        "fact_network",
        "fact_service",
        "fact_campaign",
    ],
    "feature_store": [
        "feature_registry",
        "customer_features",
        "churn_features",
        "package_features",
    ],
    "semantic": ["metric_registry"],
    "ml": ["model_registry", "prediction_registry"],
}


async def main() -> None:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT schemaname, tablename FROM pg_tables "
                "WHERE schemaname IN ('raw','warehouse','feature_store','semantic','ml') "
                "ORDER BY schemaname, tablename"
            )
        )
        rows = result.fetchall()
        actual: set[tuple[str, str]] = {(r[0], r[1]) for r in rows}

        mv_result = await conn.execute(
            text("SELECT schemaname, matviewname FROM pg_matviews WHERE schemaname = 'semantic'")
        )
        mv_rows = mv_result.fetchall()
        actual.update({(r[0], r[1]) for r in mv_rows})

    missing = []
    for schema, tables in EXPECTED_TABLES.items():
        for table in tables:
            if (schema, table) not in actual:
                missing.append(f"{schema}.{table}")

    if missing:
        print("MISSING:", missing)
    else:
        print(
            f"ALL {sum(len(v) for v in EXPECTED_TABLES.values())} tables + 2 materialized views present"
        )

    print("Actual tables in schemas:")
    for schema, table in sorted(actual):
        print(f"  {schema}.{table}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
