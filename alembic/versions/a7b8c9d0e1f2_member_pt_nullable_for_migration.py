"""마이그 데이터에 없는 컬럼 nullable로 - gender, motivation, payment_method, final_price

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-28 00:00:04.000000

기존 SaaS에서 옮겨오는 회원 데이터에 성별·결제정보·운동목적이 없을 수 있어
NOT NULL 제약 풀어둠. 사장님이 회원 상세 화면에서 사후 입력 가능.

신청서(Public POST /members, /pt-applications)는 Pydantic 단에서 여전히 필수 검증.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # members
    op.alter_column('members', 'gender', existing_type=sa.String(length=1), nullable=True)
    op.alter_column('members', 'motivation', existing_type=sa.String(length=20), nullable=True)
    op.alter_column('members', 'payment_method', existing_type=sa.String(length=20), nullable=True)
    op.alter_column('members', 'final_price', existing_type=sa.Integer(), nullable=True)
    # pt_applications
    op.alter_column('pt_applications', 'gender', existing_type=sa.String(length=1), nullable=True)
    op.alter_column('pt_applications', 'payment_method', existing_type=sa.String(length=20), nullable=True)
    op.alter_column('pt_applications', 'final_price', existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column('pt_applications', 'final_price', existing_type=sa.Integer(), nullable=False)
    op.alter_column('pt_applications', 'payment_method', existing_type=sa.String(length=20), nullable=False)
    op.alter_column('pt_applications', 'gender', existing_type=sa.String(length=1), nullable=False)
    op.alter_column('members', 'final_price', existing_type=sa.Integer(), nullable=False)
    op.alter_column('members', 'payment_method', existing_type=sa.String(length=20), nullable=False)
    op.alter_column('members', 'motivation', existing_type=sa.String(length=20), nullable=False)
    op.alter_column('members', 'gender', existing_type=sa.String(length=1), nullable=False)
