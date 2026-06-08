"""상품 4종에 duration_days·duration_hours 컬럼 추가 + PT 데이터 이관

Revision ID: r4s5t6u7v8w9
Revises: q3r4s5t6u7v8
Create Date: 2026-06-08

일권·3시간권·3+1권 같은 짧은 주기 상품을 위해 일/시간 단위 컬럼 추가.
한 상품은 (months, days, hours) 중 최대 하나만 채워짐 — 서비스 레이어에서 검증.

PT 수강권은 그동안 duration_months 컬럼을 "일" 의미로 재사용해왔음 (프론트
ptDurationDays 헬퍼 주석 참조). 이 마이그레이션에서 PT 의 기존
duration_months 값을 duration_days 로 옮기고 months 는 NULL 화 — 의미가
컬럼명과 일치하도록 정리.

비-PT(membership·locker·clothes) 의 기존 duration_months 는 그대로 둠.
"""
from alembic import op
import sqlalchemy as sa


revision = "r4s5t6u7v8w9"
down_revision = "q3r4s5t6u7v8"
branch_labels = None
depends_on = None


PASS_TABLES = (
    "membership_passes",
    "pt_passes",
    "locker_passes",
    "clothes_passes",
)


def upgrade() -> None:
    # 1) 4종 테이블에 duration_days, duration_hours nullable INT 추가
    for table in PASS_TABLES:
        op.add_column(
            table,
            sa.Column("duration_days", sa.Integer(), nullable=True),
        )
        op.add_column(
            table,
            sa.Column("duration_hours", sa.Integer(), nullable=True),
        )

    # 2) PT 수강권: duration_months → duration_days 로 의미 이관, months 는 NULL.
    #    (그동안 PT 한정으로 months 컬럼을 일 단위 저장소로 써왔음)
    op.execute(
        """
        UPDATE pt_passes
        SET duration_days = duration_months,
            duration_months = NULL
        WHERE duration_months IS NOT NULL
        """
    )


def downgrade() -> None:
    # PT 데이터 원복: duration_days → duration_months (값이 있는 것만)
    op.execute(
        """
        UPDATE pt_passes
        SET duration_months = duration_days,
            duration_days = NULL
        WHERE duration_days IS NOT NULL
        """
    )
    for table in PASS_TABLES:
        op.drop_column(table, "duration_hours")
        op.drop_column(table, "duration_days")
