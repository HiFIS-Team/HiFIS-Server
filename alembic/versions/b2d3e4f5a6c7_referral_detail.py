"""members·pt_applications에 referral_detail (기타 세부 텍스트) 추가

Revision ID: b2d3e4f5a6c7
Revises: a8c9d0e1f2g3
Create Date: 2026-05-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2d3e4f5a6c7'
down_revision: Union[str, Sequence[str], None] = 'a8c9d0e1f2g3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """유입경로 '기타' 선택 시 사용자 자유 텍스트 보관용 컬럼."""
    op.add_column(
        'members',
        sa.Column('referral_detail', sa.String(length=100), nullable=True),
    )
    op.add_column(
        'pt_applications',
        sa.Column('referral_detail', sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('pt_applications', 'referral_detail')
    op.drop_column('members', 'referral_detail')
