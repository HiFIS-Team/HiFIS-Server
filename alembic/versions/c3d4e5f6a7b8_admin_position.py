"""admins에 position (직책) 컬럼 추가

Revision ID: c3d4e5f6a7b8
Revises: b2d3e4f5a6c7
Create Date: 2026-05-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2d3e4f5a6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """관리자 직책 - SUPER_ADMIN은 NULL, FC는 MANAGER/TEAM_LEADER/TRAINER/FC."""
    op.add_column(
        'admins',
        sa.Column('position', sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('admins', 'position')
