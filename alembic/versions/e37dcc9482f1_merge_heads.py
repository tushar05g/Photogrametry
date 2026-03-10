"""merge heads

Revision ID: e37dcc9482f1
Revises: 40ed42d695fa, abcd1234efgh
Create Date: 2026-03-10 10:02:42.228639

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e37dcc9482f1'
down_revision: Union[str, Sequence[str], None] = ('40ed42d695fa', 'abcd1234efgh')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
