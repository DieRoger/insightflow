"""Inspect current dim_customer columns for canonical mapping design."""

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
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema='warehouse' AND table_name='dim_customer' ORDER BY ordinal_position"
            )
        )
        print("dim_customer columns:")
        for row in r.fetchall():
            print(f"  {row[0]} {row[1]}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
