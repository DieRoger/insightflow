"""ETL entry point — load CSV datasets into Bronze, then Silver.

Usage:
    uv run python scripts/run_etl.py --input-dir data/mock --customers 1000000
"""

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.logging import configure_logging  # noqa: E402
from app.infrastructure.database.session import engine  # noqa: E402
from app.warehouse.bronze_loader import load_bronze  # noqa: E402
from app.warehouse.silver_loader import (  # noqa: E402
    load_dimensions,
    load_facts,
    refresh_semantic_views,
)

DATASETS = ["customer", "usage", "billing", "network", "service", "campaign"]

FILE_NAMES = {
    "customer": "customer.csv",
    "usage": "usage.csv",
    "billing": "billing.csv",
    "network": "network.csv",
    "service": "service.csv",
    "campaign": "campaign.csv",
}


async def run_etl(input_dir: Path) -> dict:
    """Run the full ETL pipeline. Returns a quality report."""
    configure_logging()
    batch_id = f"etl_{datetime.now(UTC):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
    print(f"ETL batch: {batch_id}")

    report = {"batch_id": batch_id, "bronze": {}, "silver": "pending"}

    # 1. Bronze: CSV → raw.*
    for dataset in DATASETS:
        file_path = input_dir / FILE_NAMES[dataset]
        if not file_path.exists():
            print(f"  SKIP {dataset}: {file_path} not found")
            continue
        print(f"  Loading {dataset} -> raw...")
        result = await load_bronze(engine, dataset, file_path, batch_id)
        report["bronze"][dataset] = {
            "rows_total": result.rows_total,
            "rows_accepted": result.rows_accepted,
            "rows_quarantined": result.rows_quarantined,
            "quarantine_reasons": result.quarantine_reasons,
        }
        print(f"    accepted={result.rows_accepted:,} quarantined={result.rows_quarantined:,}")

    # 2. Silver: raw.* → warehouse.*
    print("  Loading dimensions...")
    await load_dimensions(engine)
    print("  Loading facts...")
    await load_facts(engine)
    print("  Refreshing semantic views...")
    await refresh_semantic_views(engine)
    report["silver"] = "completed"

    # 3. Quality report
    report_path = input_dir / f"quality_report_{batch_id}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"Quality report: {report_path}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run InsightFlow ETL pipeline")
    parser.add_argument(
        "--input-dir", type=str, default="data/mock", help="Directory with dataset CSVs"
    )
    args = parser.parse_args()
    import asyncio

    asyncio.run(run_etl(Path(args.input_dir)))


if __name__ == "__main__":
    main()
