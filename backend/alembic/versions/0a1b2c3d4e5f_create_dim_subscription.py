"""create canonical subscription dimension table

Adds the canonical `subscription` entity (data plan §7) as a warehouse
dimension: contract terms, tenure, payment method, and subscribed services
per customer. Includes dataset_id for provenance (never UNIONed sources).

Revision ID: 0a1b2c3d4e5f
Revises: f6a7b8c9d0e1
Create Date: 2026-08-14
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0a1b2c3d4e5f"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create warehouse.dim_subscription (canonical subscription entity)."""
    op.execute(
        """
        CREATE TABLE warehouse.dim_subscription (
            subscription_id BIGSERIAL PRIMARY KEY,
            source_customer_id VARCHAR(100) NOT NULL,
            dataset_id VARCHAR(50) NOT NULL,
            tenure_months INTEGER,
            contract_type VARCHAR(30),
            is_paperless_billing BOOLEAN,
            payment_method VARCHAR(100),
            phone_service BOOLEAN,
            multiple_lines BOOLEAN,
            internet_service VARCHAR(30),
            online_security BOOLEAN,
            online_backup BOOLEAN,
            device_protection BOOLEAN,
            tech_support BOOLEAN,
            streaming_tv BOOLEAN,
            streaming_movies BOOLEAN,
            loaded_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE (source_customer_id, dataset_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_sub_dataset ON warehouse.dim_subscription(dataset_id)"
    )


def downgrade() -> None:
    """Drop the subscription table (destructive — reverts the migration)."""
    op.execute("DROP TABLE IF EXISTS warehouse.dim_subscription")
