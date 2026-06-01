"""members·pt_applications에 agreed_marketing (마케팅 정보 수신 동의) 컬럼 추가

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-28 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """마케팅성 트리거(EXPIRED_FOLLOWUP 등) 발송 동의 여부 - 정보통신망법 제50조 대응.

    기존 row는 server_default=false로 일괄 처리 (보수적 - 미동의 처리).
    """
    op.add_column(
        'members',
        sa.Column(
            'agreed_marketing',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        'pt_applications',
        sa.Column(
            'agreed_marketing',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column('pt_applications', 'agreed_marketing')
    op.drop_column('members', 'agreed_marketing')
