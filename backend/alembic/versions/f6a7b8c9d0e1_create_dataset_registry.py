"""create dataset registry and data quality tables

Implements the multi-dataset governance layer (dataset_registry, raw
dataset tracking, quality reports/issues) per the InsightFlow data plan.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-14
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create dataset registry, raw dataset tracking, and quality tables."""
    op.execute("CREATE SCHEMA IF NOT EXISTS governance")

    # Dataset registry — every source dataset is registered here (never UNIONed)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS governance.dataset_registry (
            dataset_id VARCHAR(50) PRIMARY KEY,
            dataset_name VARCHAR(200) NOT NULL,
            source VARCHAR(100) NOT NULL,
            source_url VARCHAR(500),
            version VARCHAR(30),
            description TEXT,
            schema_version VARCHAR(30),
            record_count BIGINT,
            source_type VARCHAR(30),       -- 'kaggle' | 'csv' | 'parquet' | 'synthetic'
            license VARCHAR(100),
            downloaded_at TIMESTAMPTZ,
            checksum VARCHAR(64),
            status VARCHAR(20) DEFAULT 'registered',  -- registered|downloaded|validated|loaded
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )

    # Raw file tracking — each downloaded file, immutable
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS governance.raw_dataset_file (
            file_id BIGSERIAL PRIMARY KEY,
            dataset_id VARCHAR(50) NOT NULL REFERENCES governance.dataset_registry(dataset_id),
            file_name VARCHAR(255) NOT NULL,
            file_path VARCHAR(500) NOT NULL,
            checksum VARCHAR(64),
            download_time TIMESTAMPTZ DEFAULT now(),
            row_count BIGINT,
            column_count INTEGER,
            file_size_bytes BIGINT,
            UNIQUE (dataset_id, file_name)
        )
        """
    )

    # Data quality report per dataset per run
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS governance.quality_report (
            report_id BIGSERIAL PRIMARY KEY,
            dataset_id VARCHAR(50) NOT NULL REFERENCES governance.dataset_registry(dataset_id),
            run_id VARCHAR(100) NOT NULL,
            rows_total BIGINT,
            rows_valid BIGINT,
            completeness DECIMAL(5,2),
            validity DECIMAL(5,2),
            uniqueness DECIMAL(5,2),
            consistency DECIMAL(5,2),
            referential_integrity DECIMAL(5,2),
            overall_score DECIMAL(5,2),
            generated_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )

    # Detailed quality issues
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS governance.quality_issue (
            issue_id BIGSERIAL PRIMARY KEY,
            report_id BIGINT NOT NULL REFERENCES governance.quality_report(report_id),
            dataset_id VARCHAR(50) NOT NULL,
            column_name VARCHAR(100),
            rule VARCHAR(100) NOT NULL,   -- completeness|validity|uniqueness|consistency|referential_integrity
            failed_count BIGINT,
            severity VARCHAR(10) DEFAULT 'MEDIUM',  -- LOW|MEDIUM|HIGH
            sample_records JSONB,
            created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_qr_dataset ON governance.quality_report(dataset_id, generated_at DESC)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_qi_report ON governance.quality_issue(report_id)")


def downgrade() -> None:
    """Drop governance tables (destructive — reverts the migration)."""
    op.execute("DROP TABLE IF EXISTS governance.quality_issue")
    op.execute("DROP TABLE IF EXISTS governance.quality_report")
    op.execute("DROP TABLE IF EXISTS governance.raw_dataset_file")
    op.execute("DROP TABLE IF EXISTS governance.dataset_registry")
    op.execute("DROP SCHEMA IF EXISTS governance CASCADE")
