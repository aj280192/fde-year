"""partial index on active tasks

Revision ID: b7d41c2e9a05
Revises: 366e0eb74e00
Create Date: 2026-11-10 00:30:00.000000

Counting a tenant's active tasks by state read the whole table (28.6 ms on 1M rows).
This index holds only active tasks, about 10% of rows: 744 kB against 55 MB for a
full index, and the count becomes an index-only scan (0.69 ms). See the week 5
README, Results.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7d41c2e9a05"
down_revision: str | Sequence[str] | None = "366e0eb74e00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE = "state IN ('queued', 'running', 'waiting_for_input')"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_tasks_active",
        "tasks",
        ["tenant_id", "state"],
        unique=False,
        postgresql_where=sa.text(ACTIVE),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_tasks_active", table_name="tasks", postgresql_where=sa.text(ACTIVE)
    )
