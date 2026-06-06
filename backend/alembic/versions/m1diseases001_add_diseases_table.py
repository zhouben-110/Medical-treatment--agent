"""add diseases table

Revision ID: m1diseases001
Revises: d888745e3d0c
Create Date: 2026-06-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "m1diseases001"
down_revision: Union[str, Sequence[str], None] = "d888745e3d0c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "diseases",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("symptoms", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("treatment", sa.Text(), nullable=True),
        sa.Column("when_to_see_doctor", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        "ix_diseases_symptoms_gin", "diseases", ["symptoms"],
        unique=False, postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_diseases_symptoms_gin", table_name="diseases")
    op.drop_table("diseases")
