"""Verify alembic_version row exists in the database."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.infrastructure.database.session import engine  # noqa: E402


async def main() -> None:
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT version_num FROM alembic_version"))
        print("alembic_version:", result.scalar())
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
