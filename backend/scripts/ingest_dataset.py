"""Dataset ingestion — download, register, quality-gate, and preview.

Pipeline per the data plan §4-6:

    kaggle download → raw/ (immutable) → registry record →
    quality report (persisted) → canonical preview (dry-run tables)

Usage:
    uv run python scripts/ingest_dataset.py --dataset ibm_telco
    uv run python scripts/ingest_dataset.py --dataset ibm_telco --skip-download
"""

import argparse
import hashlib
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.logging import configure_logging  # noqa: E402
from app.infrastructure.database.session import engine  # noqa: E402
from app.warehouse.adapters import IBMTelcoAdapter  # noqa: E402
from app.warehouse.profiling import profile_dataframe  # noqa: E402
from app.warehouse.quality import persist_quality_report, run_quality_checks  # noqa: E402

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# Kaggle identifier → local adapter
KAGGLE_DATASETS = {
    "ibm_telco": ("blastchar/telco-customer-churn", IBMTelcoAdapter()),
}


def sha256_of(path: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


async def register_dataset(entry) -> None:
    """Upsert the dataset registry row."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO governance.dataset_registry (
                    dataset_id, dataset_name, source, source_url, version,
                    description, schema_version, source_type, license, status
                ) VALUES (
                    :id, :name, :source, :url, :version,
                    :description, :schema_version, :source_type, :license, 'registered'
                )
                ON CONFLICT (dataset_id) DO UPDATE SET
                    dataset_name = EXCLUDED.dataset_name,
                    source_url = EXCLUDED.source_url,
                    version = EXCLUDED.version,
                    status = 'registered'
                """
            ),
            {
                "id": entry.dataset_id,
                "name": entry.dataset_name,
                "source": entry.source,
                "url": entry.source_url,
                "version": entry.version,
                "description": entry.description,
                "schema_version": entry.schema_version,
                "source_type": entry.source_type,
                "license": entry.license,
            },
        )


def download_dataset(kaggle_ref: str, dest_dir: Path) -> Path | None:
    """Download a Kaggle dataset; returns the first CSV path (or None)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["kaggle", "datasets", "download", "-d", kaggle_ref, "-p", str(dest_dir), "--unzip"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"kaggle download failed: {result.stderr[-500:]}")
        return None
    csvs = sorted(dest_dir.glob("*.csv"))
    return csvs[0] if csvs else None


async def ingest(dataset_name: str, skip_download: bool = False) -> None:
    """Run the full ingestion pipeline for one dataset."""
    configure_logging()
    if dataset_name not in KAGGLE_DATASETS:
        print(f"Unknown dataset: {dataset_name}. Known: {list(KAGGLE_DATASETS)}")
        return

    kaggle_ref, adapter = KAGGLE_DATASETS[dataset_name]
    entry = adapter.registry_entry
    print(f"=== Ingesting {entry.dataset_id} ({entry.dataset_name}) ===")

    # 1. Register
    await register_dataset(entry)
    print(f"[registry] {entry.dataset_id} registered")

    # 2. Download to raw/ (immutable)
    dataset_dir = RAW_DIR / entry.dataset_id.lower()
    csv_path = None
    if not skip_download:
        csv_path = download_dataset(kaggle_ref, dataset_dir)
        if csv_path is None:
            print("[download] FAILED — check kaggle auth / network")
            return
        checksum = sha256_of(csv_path)
        print(
            f"[download] {csv_path.name} ({csv_path.stat().st_size:,} bytes, sha256={checksum[:12]}…)"
        )

        # Track raw file
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO governance.raw_dataset_file (
                        dataset_id, file_name, file_path, checksum,
                        download_time, file_size_bytes
                    ) VALUES (:id, :name, :path, :checksum, :time, :size)
                    ON CONFLICT (dataset_id, file_name) DO NOTHING
                    """
                ),
                {
                    "id": entry.dataset_id,
                    "name": csv_path.name,
                    "path": str(csv_path),
                    "checksum": checksum,
                    "time": datetime.now(UTC),
                    "size": csv_path.stat().st_size,
                },
            )
    else:
        existing = sorted(dataset_dir.glob("*.csv"))
        csv_path = existing[0] if existing else None
        if csv_path is None:
            print(f"[skip-download] no CSV found in {dataset_dir}")
            return
        print(f"[download] SKIPPED — using existing {csv_path.name}")

    # 3. Load raw + profile + run quality checks
    df = adapter.load_raw(csv_path)
    print(f"[raw] {len(df):,} rows × {df.shape[1]} cols")

    # Dataset profiling — descriptive stats before quality gating
    profiling_report = profile_dataframe(df, entry.dataset_id)
    print("\n=== Dataset Profile ===")
    print(
        f"Dataset: {entry.dataset_id}   Shape: {profiling_report.rows:,} × {profiling_report.columns}"
    )
    for ns in profiling_report.numeric[:5]:
        print(
            f"  [num] {ns.column}: missing={ns.missing} ({ns.missing_ratio:.1%}), "
            f"range=[{ns.min}, {ns.max}], mean={ns.mean:.2f}, std={ns.std:.2f}"
        )
    for cs in profiling_report.categorical[:5]:
        print(
            f"  [cat] {cs.column}: missing={cs.missing} ({cs.missing_ratio:.1%}), "
            f"unique={cs.unique}, top={cs.top_values[:2]}"
        )

    report = run_quality_checks(
        df,
        dataset_id=entry.dataset_id,
        column_rules=adapter.quality_column_rules(),
        consistency_rules=adapter.quality_consistency_rules(),
        unique_keys=adapter.unique_keys(),
    )
    print("\n=== Data Quality Report ===")
    print(f"Dataset: {entry.dataset_id}   Rows: {report.rows_total:,}")
    print(f"  Completeness        {report.completeness}%")
    print(f"  Validity            {report.validity}%")
    print(f"  Uniqueness          {report.uniqueness}%")
    print(f"  Consistency         {report.consistency}%")
    print(f"  ReferentialIntegrity {report.referential_integrity}%")
    print(f"  Overall Score       {report.overall_score}%")
    for issue in report.issues:
        print(
            f"  [WARN:{issue.severity}] {issue.column}:{issue.rule} - {issue.failed_count:,} failed"
        )

    report_id = await persist_quality_report(engine, report)
    print(f"\n[quality] report persisted (id={report_id})")

    # 4. Canonical preview (dry-run — canonical tables not yet loaded)
    canonical = adapter.to_canonical(df)
    print("\n=== Canonical Preview ===")
    for table, tdf in canonical.items():
        print(
            f"  {table}: {len(tdf):,} rows, cols={list(tdf.columns)[:6]}{'…' if len(tdf.columns) > 6 else ''}"
        )

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a Kaggle dataset into InsightFlow")
    parser.add_argument(
        "--dataset", required=True, choices=list(KAGGLE_DATASETS), help="Dataset key"
    )
    parser.add_argument("--skip-download", action="store_true", help="Use already-downloaded CSV")
    args = parser.parse_args()
    import asyncio

    asyncio.run(ingest(args.dataset, skip_download=args.skip_download))


if __name__ == "__main__":
    main()
