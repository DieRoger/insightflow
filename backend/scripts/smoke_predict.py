"""End-to-end prediction smoke test: predict a few customers."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.infrastructure.database.session import engine  # noqa: E402
from app.ml.predict import predict_batch, predict_customer  # noqa: E402


async def main() -> None:
    # Online prediction for a churned customer
    async with engine.connect() as conn:
        from sqlalchemy import text

        result = await conn.execute(
            text(
                "SELECT source_customer_id FROM warehouse.dim_customer "
                "WHERE status = 'churned' LIMIT 1"
            )
        )
        row = result.fetchone()
        churned_id = row[0] if row else None

        result = await conn.execute(
            text(
                "SELECT source_customer_id FROM warehouse.dim_customer "
                "WHERE status = 'active' LIMIT 1"
            )
        )
        row = result.fetchone()
        active_id = row[0] if row else None

    if churned_id:
        pred = await predict_customer(engine, churned_id)
        print(
            f"Churned customer {churned_id}: risk={pred['risk_score']} level={pred['risk_level']}"
        )
        print(f"  top factors: {pred['top_positive_factors'][:2]}")
    if active_id:
        pred = await predict_customer(engine, active_id)
        print(f"Active customer {active_id}: risk={pred['risk_score']} level={pred['risk_level']}")

    # Batch prediction
    count = await predict_batch(engine)
    print(f"Batch prediction: {count} customers")

    # Verify registry
    async with engine.connect() as conn:
        from sqlalchemy import text

        result = await conn.execute(
            text(
                "SELECT prediction_type, COUNT(*) FROM ml.prediction_registry GROUP BY prediction_type"
            )
        )
        print("prediction registry:", result.fetchall())

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
