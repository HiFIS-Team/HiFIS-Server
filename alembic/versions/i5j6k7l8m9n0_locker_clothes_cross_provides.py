"""LockerPass·ClothesPass에 서로의 무료 제공 플래그 추가

Revision ID: i5j6k7l8m9n0
Revises: h4i5j6k7l8m9
Create Date: 2026-05-29

- LockerPass.provides_clothes : 락커가 운동복도 무료 제공 (예: '락커 6개월 + 운동복 무료')
- ClothesPass.provides_locker : 운동복이 락커도 무료 제공 (예: '운동복 1개월 (락커 무료)')

양방향 설정 가능. 사장님이 운영 정책에 따라 어드민 폼에서 토글.
기존 행은 false 디폴트.
"""
from alembic import op
import sqlalchemy as sa


revision = "i5j6k7l8m9n0"
down_revision = "h4i5j6k7l8m9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "locker_passes",
        sa.Column(
            "provides_clothes",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "clothes_passes",
        sa.Column(
            "provides_locker",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("clothes_passes", "provides_locker")
    op.drop_column("locker_passes", "provides_clothes")
