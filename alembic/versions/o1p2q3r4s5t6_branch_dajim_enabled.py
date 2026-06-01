"""branches에 dajim_enabled 컬럼 추가 - 지점별 다짐 자동 등록 토글

Revision ID: o1p2q3r4s5t6
Revises: n0o1p2q3r4s5
Create Date: 2026-06-01

회원가입 직후 다짐(Dagym)에도 자동 INSERT 시도하는 통합 토글.
첨단점·동광주점 대상이지만 현재 동광주점만 활성. 디폴트 false.
브로제이 토글과 독립 - 둘 다 켤 수도, 한 쪽만 켤 수도 있음.
"""
from alembic import op
import sqlalchemy as sa


revision = "o1p2q3r4s5t6"
down_revision = "n0o1p2q3r4s5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "branches",
        sa.Column(
            "dajim_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("branches", "dajim_enabled")
