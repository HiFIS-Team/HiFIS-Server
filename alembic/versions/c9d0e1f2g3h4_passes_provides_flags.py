"""membership_passes·pt_passes에 provides_locker/provides_clothes 플래그 추가

Revision ID: c9d0e1f2g3h4
Revises: b8c9d0e1f2g3
Create Date: 2026-05-29

회원권/수강권에 락커·운동복 무료제공 여부 추가.
신청 시 True면 락커·운동복 선택 차단 + 가격 합산 제외.
기존 행은 server_default=false 적용 → 사장님이 어드민에서 개별 토글.
"""
from alembic import op
import sqlalchemy as sa


revision = "c9d0e1f2g3h4"
down_revision = "b8c9d0e1f2g3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("membership_passes", "pt_passes"):
        op.add_column(
            table,
            sa.Column(
                "provides_locker",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "provides_clothes",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    for table in ("membership_passes", "pt_passes"):
        op.drop_column(table, "provides_clothes")
        op.drop_column(table, "provides_locker")
