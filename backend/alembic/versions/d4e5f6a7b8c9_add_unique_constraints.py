"""add unique constraints for upsert targets

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add unique constraints required by ON CONFLICT upserts."""
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_dim_package_source ON warehouse.dim_package (source_package_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_dim_customer_source ON warehouse.dim_customer (source_customer_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_dim_region_city_province ON warehouse.dim_region (city, province)"
    )


def downgrade() -> None:
    """Drop the unique constraints (destructive — reverts the migration)."""
    op.execute("DROP INDEX IF EXISTS warehouse.uq_dim_region_city_province")
    op.execute("DROP INDEX IF EXISTS warehouse.uq_dim_customer_source")
    op.execute("DROP INDEX IF EXISTS warehouse.uq_dim_package_source")
