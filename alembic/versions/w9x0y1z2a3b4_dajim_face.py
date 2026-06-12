"""다짐 얼굴 등록 컬럼 추가 (branches.dajim_face_enabled, members·pts.dajim_id/face_registered)

Revision ID: w9x0y1z2a3b4
Revises: v8w9x0y1z2a3
Create Date: 2026-06-12

첨단점 회원가입·PT 신청 시 얼굴 사진 받아 다짐 RegisterFace 호출.
- 다짐 회원 UUID(dajim_id) + 얼굴 등록 상태(dajim_face_registered) 저장
- 첨단점 dajim_face_enabled = True seed (운영 즉시 활성)
- 동광주는 지문 인증이라 False 유지
"""
from alembic import op
import sqlalchemy as sa


revision = "w9x0y1z2a3b4"
down_revision = "v8w9x0y1z2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 옛 다짐 작업의 잔재 컬럼이 일부 환경에 남아있어 idempotent하게 처리.
    # PG IF NOT EXISTS로 컬럼별 안전 추가.
    op.execute(
        "ALTER TABLE branches ADD COLUMN IF NOT EXISTS "
        "dajim_face_enabled BOOLEAN NOT NULL DEFAULT false"
    )
    # 첨단점 활성화 (이미 true여도 무동작)
    op.execute(
        "UPDATE branches SET dajim_face_enabled = true "
        "WHERE name = '피트니스스타 첨단점'"
    )

    for table in ("members", "pt_applications"):
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "
            "dajim_id VARCHAR(64)"
        )
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "
            "dajim_face_registered BOOLEAN"
        )


def downgrade() -> None:
    for table in ("members", "pt_applications"):
        op.drop_column(table, "dajim_face_registered")
        op.drop_column(table, "dajim_id")
    op.drop_column("branches", "dajim_face_enabled")
