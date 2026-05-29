"""Member·PTApplication birth_date nullable - 마이그 회원 일부 미입력 대응

Revision ID: b8c9d0e1f2g3
Revises: a7b8c9d0e1f2
Create Date: 2026-05-28 00:00:05.000000

옛 SaaS에서 생년월일을 "미입력"으로 두는 회원이 일부 있어 NOT NULL 제약 풀어둠.
신청서(POST /members, /pt-applications)는 Pydantic 단에서 여전히 필수 검증.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8c9d0e1f2g3'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('members', 'birth_date', existing_type=sa.Date(), nullable=True)
    op.alter_column('pt_applications', 'birth_date', existing_type=sa.Date(), nullable=True)


def downgrade() -> None:
    op.alter_column('pt_applications', 'birth_date', existing_type=sa.Date(), nullable=False)
    op.alter_column('members', 'birth_date', existing_type=sa.Date(), nullable=False)
