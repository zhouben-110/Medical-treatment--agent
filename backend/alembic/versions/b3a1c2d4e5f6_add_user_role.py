"""add_user_role

Revision ID: b3a1c2d4e5f6
Revises: 0ddb60a7fa10
Create Date: 2026-06-20 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b3a1c2d4e5f6'
down_revision: Union[str, Sequence[str], None] = '0ddb60a7fa10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role', sa.String(), nullable=True, server_default='user'))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('role')
