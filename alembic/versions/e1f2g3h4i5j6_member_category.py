"""members 테이블에 category 컬럼 추가 - NEW(신규) / EXISTING(재등록)

Revision ID: e1f2g3h4i5j6
Revises: d0e1f2g3h4i5
Create Date: 2026-05-29

신청 진입 경로에 따라 자동 분류:
- POST /members → NEW (신규 가입)
- POST /members/re-register → 기존 행 UPDATE + category=EXISTING

기존 데이터는 모두 NEW로 채워짐 (server_default).
재등록 endpoint 호출 시점에만 EXISTING으로 갱신됨.
"""
from alembic import op
import sqlalchemy as sa


revision = "e1f2g3h4i5j6"
down_revision = "d0e1f2g3h4i5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "members",
        sa.Column(
            "category",
            sa.String(20),
            nullable=False,
            server_default="NEW",
        ),
    )


def downgrade() -> None:
    op.drop_column("members", "category")
