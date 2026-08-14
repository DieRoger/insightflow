"""List model registry state + restore a production model if missing."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.infrastructure.database.session import engine  # noqa: E402


async def main() -> None:
    async with engine.connect() as conn:
        r = await conn.execute(
            text(
                "SELECT model_id, model_name, model_version, status "
                "FROM ml.model_registry ORDER BY model_id DESC LIMIT 10"
            )
        )
        for row in r.fetchall():
            print(row)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
