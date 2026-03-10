"""add progress and updated_at to scan_jobs

Revision ID: abcd1234efgh
Revises: 900a2513b481
Create Date: 2026-03-10 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'abcd1234efgh'
down_revision: Union[str, Sequence[str], None] = '900a2513b481'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('scan_jobs', sa.Column('progress', sa.String(), nullable=True))
    op.add_column('scan_jobs', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('scan_jobs', 'progress')
    op.drop_column('scan_jobs', 'updated_at')