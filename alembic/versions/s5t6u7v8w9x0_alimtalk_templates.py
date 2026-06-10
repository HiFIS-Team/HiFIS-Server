"""alimtalk_templates 테이블 + 전체 TriggerType enum seed

Revision ID: s5t6u7v8w9x0
Revises: r4s5t6u7v8w9
Create Date: 2026-06-09

트리거별 알림톡 발송 토글 - 사장님이 어드민에서 ON/OFF.
기존 MessageTemplate(본문 수정)과 별개 테이블 - 책임 분리.

seed: TriggerType enum 14종 모두 row 생성, is_enabled=True 디폴트.
새 트리거 추가 시 별도 마이그에서 INSERT 필요.
"""
import uuid

from alembic import op
import sqlalchemy as sa


revision = "s5t6u7v8w9x0"
down_revision = "r4s5t6u7v8w9"
branch_labels = None
depends_on = None


# TriggerType enum 전체 (app/schemas/enums.py와 동일)
TRIGGER_TYPES = [
    "RESERVATION_CONFIRM",
    "REGISTERED",
    "RE_REGISTERED",
    "HOLD",
    "HOLD_CANCEL",
    "RESERVATION_CHECK_1",
    "RESERVATION_CHECK_2",
    "D_PLUS_7",
    "D_PLUS_14",
    "D_PLUS_30",
    "EXPIRY_SOON_5",
    "EXPIRY_SOON_2",
    "EXPIRED_TODAY",
    "EXPIRED_FOLLOWUP",
]


def upgrade() -> None:
    op.create_table(
        "alimtalk_templates",
        sa.Column(
            "id", sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True, nullable=False,
        ),
        sa.Column("trigger_type", sa.String(50), nullable=False, unique=True),
        sa.Column(
            "is_enabled", sa.Boolean,
            nullable=False, server_default=sa.text("true"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_alimtalk_templates_trigger_type",
        "alimtalk_templates", ["trigger_type"],
    )

    # 전체 트리거 seed - is_enabled=True 디폴트
    table = sa.table(
        "alimtalk_templates",
        sa.column("id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.column("trigger_type", sa.String(50)),
    )
    op.bulk_insert(
        table,
        [{"id": uuid.uuid4(), "trigger_type": t} for t in TRIGGER_TYPES],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_alimtalk_templates_trigger_type", table_name="alimtalk_templates",
    )
    op.drop_table("alimtalk_templates")
