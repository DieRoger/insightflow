"""create schemas and bronze raw tables

Revision ID: a1b2c3d4e5f6
Revises: 58d690bcbe1e
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa  # noqa: F401  # reserved for future model metadata

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "58d690bcbe1e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _exec(sql: str) -> None:
    """Execute a multi-statement DDL script statement by statement.

    asyncpg's prepared-statement protocol rejects multi-command strings,
    so each statement must be executed separately.
    """
    for stmt in sql.split(";"):
        if stmt.strip():
            op.execute(stmt)


RAW_TABLES = {
    "raw_customer": """
        CREATE TABLE raw.raw_customer (
            raw_id BIGSERIAL PRIMARY KEY,
            customer_id VARCHAR(50) NOT NULL,
            gender VARCHAR(10),
            age INTEGER,
            city VARCHAR(100),
            province VARCHAR(100),
            join_date DATE NOT NULL,
            contract_type VARCHAR(30) NOT NULL,
            package_id VARCHAR(50) NOT NULL,
            package_name VARCHAR(100),
            status VARCHAR(20) NOT NULL,
            import_batch_id VARCHAR(100) NOT NULL,
            imported_at TIMESTAMPTZ DEFAULT now(),
            source_filename VARCHAR(255)
        );
        CREATE INDEX idx_raw_customer_id ON raw.raw_customer(customer_id);
        CREATE INDEX idx_raw_customer_batch ON raw.raw_customer(import_batch_id);
    """,
    "raw_usage": """
        CREATE TABLE raw.raw_usage (
            raw_id BIGSERIAL PRIMARY KEY,
            customer_id VARCHAR(50) NOT NULL,
            usage_date DATE NOT NULL,
            voice_minutes DECIMAL(10,2),
            sms_count INTEGER,
            data_usage_mb DECIMAL(12,2),
            roaming_usage_mb DECIMAL(10,2),
            peak_usage_mb DECIMAL(10,2),
            international_minutes DECIMAL(8,2),
            import_batch_id VARCHAR(100) NOT NULL,
            imported_at TIMESTAMPTZ DEFAULT now(),
            source_filename VARCHAR(255)
        );
        CREATE INDEX idx_raw_usage_customer ON raw.raw_usage(customer_id, usage_date);
        CREATE INDEX idx_raw_usage_batch ON raw.raw_usage(import_batch_id);
    """,
    "raw_billing": """
        CREATE TABLE raw.raw_billing (
            raw_id BIGSERIAL PRIMARY KEY,
            customer_id VARCHAR(50) NOT NULL,
            billing_month DATE NOT NULL,
            monthly_fee DECIMAL(10,2) NOT NULL,
            discount_amount DECIMAL(10,2),
            payment_status VARCHAR(20) NOT NULL,
            overdue_days INTEGER,
            package_price DECIMAL(10,2) NOT NULL,
            payment_method VARCHAR(30),
            import_batch_id VARCHAR(100) NOT NULL,
            imported_at TIMESTAMPTZ DEFAULT now(),
            source_filename VARCHAR(255)
        );
        CREATE INDEX idx_raw_billing_customer ON raw.raw_billing(customer_id, billing_month);
        CREATE INDEX idx_raw_billing_batch ON raw.raw_billing(import_batch_id);
    """,
    "raw_network": """
        CREATE TABLE raw.raw_network (
            raw_id BIGSERIAL PRIMARY KEY,
            customer_id VARCHAR(50) NOT NULL,
            measurement_date DATE NOT NULL,
            latency_ms DECIMAL(8,2),
            signal_strength DECIMAL(5,2),
            drop_rate DECIMAL(5,4),
            packet_loss DECIMAL(5,4),
            coverage_score DECIMAL(5,2),
            import_batch_id VARCHAR(100) NOT NULL,
            imported_at TIMESTAMPTZ DEFAULT now(),
            source_filename VARCHAR(255)
        );
        CREATE INDEX idx_raw_network_customer ON raw.raw_network(customer_id, measurement_date);
        CREATE INDEX idx_raw_network_batch ON raw.raw_network(import_batch_id);
    """,
    "raw_service": """
        CREATE TABLE raw.raw_service (
            raw_id BIGSERIAL PRIMARY KEY,
            customer_id VARCHAR(50) NOT NULL,
            ticket_date DATE NOT NULL,
            ticket_count INTEGER NOT NULL,
            complaint_type VARCHAR(50),
            waiting_time_min DECIMAL(8,2),
            resolution_time_min DECIMAL(8,2),
            csat_score INTEGER,
            escalation_count INTEGER,
            import_batch_id VARCHAR(100) NOT NULL,
            imported_at TIMESTAMPTZ DEFAULT now(),
            source_filename VARCHAR(255)
        );
        CREATE INDEX idx_raw_service_customer ON raw.raw_service(customer_id, ticket_date);
        CREATE INDEX idx_raw_service_batch ON raw.raw_service(import_batch_id);
    """,
    "raw_campaign": """
        CREATE TABLE raw.raw_campaign (
            raw_id BIGSERIAL PRIMARY KEY,
            customer_id VARCHAR(50) NOT NULL,
            campaign_id VARCHAR(50) NOT NULL,
            campaign_date DATE NOT NULL,
            promotion_type VARCHAR(50),
            coupon_used BOOLEAN,
            converted BOOLEAN,
            channel VARCHAR(30),
            campaign_cost DECIMAL(10,2),
            import_batch_id VARCHAR(100) NOT NULL,
            imported_at TIMESTAMPTZ DEFAULT now(),
            source_filename VARCHAR(255)
        );
        CREATE INDEX idx_raw_campaign_customer ON raw.raw_campaign(customer_id, campaign_date);
        CREATE INDEX idx_raw_campaign_batch ON raw.raw_campaign(import_batch_id);
    """,
}


def upgrade() -> None:
    """Create schemas and raw (Bronze) append-only tables."""
    for schema in ("raw", "warehouse", "feature_store", "semantic", "ml"):
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    for _table_name, ddl in RAW_TABLES.items():
        _exec(ddl)

    # Bronze immutability: revoke write access from all non-ETL roles at the
    # application level is enforced by AR-010. For MVP single-user setup the
    # application user retains full rights; multi-role enforcement lands with RBAC.


def downgrade() -> None:
    """Drop raw tables and schemas (destructive — reverts the migration)."""
    for table_name in reversed(list(RAW_TABLES.keys())):
        op.execute(f"DROP TABLE IF EXISTS raw.{table_name}")
    for schema in ("ml", "semantic", "feature_store", "warehouse", "raw"):
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
