"""branches에 broj_enabled 컬럼 추가 - 지점별 브로제이 자동 등록 토글

Revision ID: n0o1p2q3r4s5
Revises: k7l8m9n0o1p2
Create Date: 2026-06-01

회원가입 직후 브로제이(BroJ)에도 자동 INSERT 시도하는 통합 토글.
화순점만 운영 중이라 디폴트 false. 사장님이 어드민에서 화순점만 ON.
"""
from alembic import op
import sqlalchemy as sa


revision = "n0o1p2q3r4s5"
down_revision = "k7l8m9n0o1p2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "branches",
        sa.Column(
            "broj_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("branches", "broj_enabled")
