"""system_config 테이블 추가 - 시스템 운영 토글 (단일 행)

Revision ID: j6k7l8m9n0o1
Revises: i5j6k7l8m9n0
Create Date: 2026-05-30

어드민에서 즉시 변경 가능한 운영 플래그.
- messaging_enabled : SMS·알림톡 실 발송 여부 (false면 send_message가 차단)

단일 행 패턴 (id=1 고정). 디폴트 messaging_enabled=false (안전).
환경변수 MESSAGING_ENABLED는 이제 무시 - DB 토글이 우선.
"""
from alembic import op
import sqlalchemy as sa


revision = "j6k7l8m9n0o1"
down_revision = "i5j6k7l8m9n0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "messaging_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # 단일 행 INSERT (id=1, messaging_enabled=false)
    op.execute("INSERT INTO system_config (id, messaging_enabled) VALUES (1, false)")


def downgrade() -> None:
    op.drop_table("system_config")
