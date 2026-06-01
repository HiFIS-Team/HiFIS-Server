"""상품 4종에 duration_months 컬럼 추가 - 이용 기간(개월)

Revision ID: h4i5j6k7l8m9
Revises: g3h4i5j6k7l8
Create Date: 2026-05-29

회원권/수강권/락커/운동복에 "이용 기간(개월)" 컬럼 추가.
프론트 신청서가 회원권 선택 시 start_date + duration_months로 end_date 자동 계산.

nullable - 일권·2주권·PT 회당 등 예외 케이스는 NULL로 둠.
기존 행은 NULL로 채워짐 (사장님이 어드민 폼에서 추후 입력).
"""
from alembic import op
import sqlalchemy as sa


revision = "h4i5j6k7l8m9"
down_revision = "g3h4i5j6k7l8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("membership_passes", "pt_passes", "locker_passes", "clothes_passes"):
        op.add_column(
            table,
            sa.Column("duration_months", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    for table in ("membership_passes", "pt_passes", "locker_passes", "clothes_passes"):
        op.drop_column(table, "duration_months")
