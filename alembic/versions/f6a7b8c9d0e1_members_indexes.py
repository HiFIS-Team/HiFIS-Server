"""members·pt_applications 자주 쓰는 쿼리용 인덱스 추가

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-28 00:00:03.000000

회원 ~3000명 마이그레이션 대비:
- (branch_id, status): FC 본인 지점 활성 회원 목록
- (phone): 전화번호 검색 (이미 비슷한 패턴 있을 수 있으나 명시 인덱스)
- (end_date): 스케줄러 매일 만기 +N일 도래자 탐색
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'ix_members_branch_status', 'members', ['branch_id', 'status'],
    )
    op.create_index('ix_members_phone', 'members', ['phone'])
    op.create_index('ix_members_end_date', 'members', ['end_date'])

    op.create_index(
        'ix_pt_applications_branch_status',
        'pt_applications', ['branch_id', 'status'],
    )
    op.create_index('ix_pt_applications_phone', 'pt_applications', ['phone'])
    op.create_index('ix_pt_applications_end_date', 'pt_applications', ['end_date'])


def downgrade() -> None:
    op.drop_index('ix_pt_applications_end_date', 'pt_applications')
    op.drop_index('ix_pt_applications_phone', 'pt_applications')
    op.drop_index('ix_pt_applications_branch_status', 'pt_applications')
    op.drop_index('ix_members_end_date', 'members')
    op.drop_index('ix_members_phone', 'members')
    op.drop_index('ix_members_branch_status', 'members')
