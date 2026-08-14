"""initial empty migration

Revision ID: 58d690bcbe1e
Revises:
Create Date: 2026-08-12 09:29:14.814682

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "58d690bcbe1e"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
