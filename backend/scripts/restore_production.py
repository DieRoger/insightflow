"""Restore the production churn model."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.infrastructure.database.session import engine  # noqa: E402


async def main() -> None:
    async with engine.begin() as conn:
        # Archive any current production, then promote the newest real LR model
        await conn.execute(
            text(
                "UPDATE ml.model_registry SET status = 'archived' "
                "WHERE status = 'production' AND model_type = 'churn_prediction'"
            )
        )
        await conn.execute(
            text(
                "UPDATE ml.model_registry SET status = 'production', promoted_at = now() "
                "WHERE model_id = (SELECT model_id FROM ml.model_registry "
                "WHERE model_name = 'churn_logistic_regression' ORDER BY model_id DESC LIMIT 1)"
            )
        )
    print("production restored")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
