"""alimtalk_templates 지점별 분리 (branch_id 추가)

Revision ID: v8w9x0y1z2a3
Revises: u7v8w9x0y1z2
Create Date: 2026-06-12

지점마다 트리거를 독립적으로 토글·편집할 수 있도록 (branch_id, trigger_type)
복합 unique로 전환.

마이그 절차:
1. branch_id 컬럼 NULLABLE로 추가 (기존 row 보존)
2. trigger_type 의 단일 unique 제거
3. 각 기존 row를 모든 지점에 복제 (현 body·is_enabled 그대로)
4. 원본 NULL branch_id row 삭제
5. branch_id NOT NULL + (branch_id, trigger_type) 복합 unique 추가
"""
import uuid

from alembic import op
import sqlalchemy as sa


revision = "v8w9x0y1z2a3"
down_revision = "u7v8w9x0y1z2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. branch_id 컬럼 추가 (NULLABLE 시작 - 기존 row 깨지지 않게)
    op.add_column(
        "alimtalk_templates",
        sa.Column(
            "branch_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("branches.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_alimtalk_templates_branch_id",
        "alimtalk_templates", ["branch_id"],
    )

    # 2. 옛 단일 unique 제거 (테이블 생성 마이그에서 unique=True로 박힌 거)
    bind = op.get_bind()
    # PG 자동 생성 unique constraint 이름 조회 후 제거
    bind.execute(sa.text("""
        DO $$
        DECLARE
            cname TEXT;
        BEGIN
            SELECT conname INTO cname
            FROM pg_constraint
            WHERE conrelid = 'alimtalk_templates'::regclass
              AND contype = 'u'
              AND conname LIKE '%trigger_type%';
            IF cname IS NOT NULL THEN
                EXECUTE 'ALTER TABLE alimtalk_templates DROP CONSTRAINT ' || cname;
            END IF;
        END $$;
    """))

    # 3. 각 지점에 14 row 복제 (현 body·is_enabled 보존)
    bind.execute(sa.text("""
        INSERT INTO alimtalk_templates
            (id, branch_id, trigger_type, is_enabled, body, updated_at)
        SELECT
            gen_random_uuid(), b.id, t.trigger_type, t.is_enabled, t.body, NOW()
        FROM branches b
        CROSS JOIN (
            SELECT trigger_type, is_enabled, body
            FROM alimtalk_templates
            WHERE branch_id IS NULL
        ) t
    """))

    # 4. 원본 NULL row 삭제
    bind.execute(sa.text(
        "DELETE FROM alimtalk_templates WHERE branch_id IS NULL"
    ))

    # 5. NOT NULL + 복합 unique
    op.alter_column(
        "alimtalk_templates", "branch_id", nullable=False,
    )
    op.create_unique_constraint(
        "uq_alimtalk_templates_branch_trigger",
        "alimtalk_templates", ["branch_id", "trigger_type"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_alimtalk_templates_branch_trigger",
        "alimtalk_templates", type_="unique",
    )
    op.drop_index(
        "ix_alimtalk_templates_branch_id", table_name="alimtalk_templates",
    )
    op.drop_column("alimtalk_templates", "branch_id")
    # 단일 unique는 알아서 다시 안 만듦 (이전 마이그 재실행 필요)
