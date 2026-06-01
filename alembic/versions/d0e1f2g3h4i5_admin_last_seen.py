"""admins 테이블에 last_seen_at 추가 - SUPER_ADMIN 접속 현황용

Revision ID: d0e1f2g3h4i5
Revises: c9d0e1f2g3h4
Create Date: 2026-05-29

heartbeat 엔드포인트(POST /admin/me/heartbeat)가 갱신하는 컬럼.
NULL이면 한 번도 heartbeat 없었던 신규 가입자 → is_online=False.
"""
from alembic import op
import sqlalchemy as sa


revision = "d0e1f2g3h4i5"
down_revision = "c9d0e1f2g3h4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "admins",
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("admins", "last_seen_at")
