"""add_user_auth_fields

Revision ID: 0ddb60a7fa10
Revises: m1diseases001
Create Date: 2026-06-19 16:42:41.614631

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0ddb60a7fa10'
down_revision: Union[str, Sequence[str], None] = 'm1diseases001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 添加 email 和 is_active 字段到 users 表
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'))
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    # 移除 email 和 is_active 字段
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_email'))
        batch_op.drop_column('is_active')
        batch_op.drop_column('email')
