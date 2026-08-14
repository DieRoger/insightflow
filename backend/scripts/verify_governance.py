"""Verify governance schema contents after IBM Telco ingestion."""

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
                "SELECT dataset_id, dataset_name, status, source_type FROM governance.dataset_registry"
            )
        )
        print("registry:", r.fetchall())

        r = await conn.execute(
            text("SELECT dataset_id, file_name, file_size_bytes FROM governance.raw_dataset_file")
        )
        print("raw files:", r.fetchall())

        r = await conn.execute(
            text(
                "SELECT dataset_id, rows_total, overall_score, generated_at::date FROM governance.quality_report ORDER BY report_id DESC LIMIT 3"
            )
        )
        print("quality reports:", r.fetchall())

        r = await conn.execute(
            text(
                "SELECT dataset_id, column_name, rule, failed_count, severity FROM governance.quality_issue ORDER BY issue_id DESC LIMIT 4"
            )
        )
        print("issues:", r.fetchall())
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
