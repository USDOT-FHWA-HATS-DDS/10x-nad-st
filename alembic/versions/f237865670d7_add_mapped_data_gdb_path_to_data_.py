"""add mapped_data_gdb_path to data_submissions

Revision ID: f237865670d7
Revises: 558f8d429963
Create Date: 2026-04-16 11:32:20.281381

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f237865670d7'
down_revision: Union[str, None] = '558f8d429963'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('data_submissions', sa.Column('mapped_data_gdb_path', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('data_submissions', 'mapped_data_gdb_path')
