"""브로제이 얼굴 등록 컬럼 + 화순점 broj_face_enabled seed

Revision ID: x0y1z2a3b4c5
Revises: w9x0y1z2a3b4
Create Date: 2026-06-12

화순점 회원가입·PT 신청 시 얼굴 사진 받아 broj 등록 (다짐 패턴과 동일).
- Branch.broj_face_enabled (화순점 = True seed)
- Member/PTApplication.broj_id, broj_face_registered
"""
from alembic import op
import sqlalchemy as sa


revision = "x0y1z2a3b4c5"
down_revision = "w9x0y1z2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # idempotent (옛 잔재 대응)
    op.execute(
        "ALTER TABLE branches ADD COLUMN IF NOT EXISTS "
        "broj_face_enabled BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute(
        "UPDATE branches SET broj_face_enabled = true "
        "WHERE name = '피트니스스타 화순점'"
    )

    for table in ("members", "pt_applications"):
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS broj_id VARCHAR(32)"
        )
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "
            "broj_face_registered BOOLEAN"
        )


def downgrade() -> None:
    for table in ("members", "pt_applications"):
        op.drop_column(table, "broj_face_registered")
        op.drop_column(table, "broj_id")
    op.drop_column("branches", "broj_face_enabled")
