"""pt_applications 테이블에 category 컬럼 추가 - NEW(신규) / EXISTING(재등록)

Revision ID: f2g3h4i5j6k7
Revises: e1f2g3h4i5j6
Create Date: 2026-05-29

PT 재등록 endpoint(/pt-applications/re-register) 도입에 따른 컬럼 추가.
회원과 동일한 패턴 (Member.category).
"""
from alembic import op
import sqlalchemy as sa


revision = "f2g3h4i5j6k7"
down_revision = "e1f2g3h4i5j6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pt_applications",
        sa.Column(
            "category",
            sa.String(20),
            nullable=False,
            server_default="NEW",
        ),
    )


def downgrade() -> None:
    op.drop_column("pt_applications", "category")
