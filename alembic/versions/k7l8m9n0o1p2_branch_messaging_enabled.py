"""branches에 messaging_enabled 컬럼 추가 - 지점별 알림톡 토글

Revision ID: k7l8m9n0o1p2
Revises: j6k7l8m9n0o1
Create Date: 2026-05-30

전역(SystemConfig) + 지점별(Branch) 이중 토글:
- 둘 다 true여야 send_message가 발송
- 어느 한 쪽이라도 false면 이력 INSERT·발송 모두 스킵

기존 지점들은 false 디폴트 → 운영 시작 시 SUPER_ADMIN이 지점별로 켜야 함.
"""
from alembic import op
import sqlalchemy as sa


revision = "k7l8m9n0o1p2"
down_revision = "j6k7l8m9n0o1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "branches",
        sa.Column(
            "messaging_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("branches", "messaging_enabled")
