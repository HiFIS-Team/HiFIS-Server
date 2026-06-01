"""members·pt_applications에 total_paid 컬럼 추가 - 누적 결제 금액

Revision ID: g3h4i5j6k7l8
Revises: f2g3h4i5j6k7
Create Date: 2026-05-29

final_price = 이번 결제 금액 (재등록 시 새 값으로 덮어씀)
total_paid  = 지금까지 누적 결제 금액 (재등록 시 += 이번 결제)

신규 가입은 final_price = total_paid 같은 값. 재등록만 분리됨.

기존 행은 final_price 값을 total_paid에도 복사 (마이그 회원 = 첫 결제 = 누적).
화순점 테스트 데이터(재등록 흐름으로 누적된 final_price 값) 은 별도 정리 권장.
"""
from alembic import op
import sqlalchemy as sa


revision = "g3h4i5j6k7l8"
down_revision = "f2g3h4i5j6k7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("members", "pt_applications"):
        op.add_column(
            table,
            sa.Column("total_paid", sa.Integer(), nullable=True),
        )
        # 기존 행 초기화 - final_price를 total_paid에 복사
        op.execute(f"UPDATE {table} SET total_paid = final_price")


def downgrade() -> None:
    for table in ("members", "pt_applications"):
        op.drop_column(table, "total_paid")
