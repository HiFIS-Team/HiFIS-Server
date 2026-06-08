"""members·pt_applications에 signature_url 컬럼 추가 - 전자서명 PNG 저장 경로

Revision ID: q3r4s5t6u7v8
Revises: p2q3r4s5t6u7
Create Date: 2026-06-05

다짐 지점(첨단·동광주)만 신청서 작성 시 전자서명을 받고, 그 외 지점은 NULL.
값 형식: '/uploads/signatures/<uuid>.png' - FastAPI StaticFiles로 노출.
"""
from alembic import op
import sqlalchemy as sa


revision = "q3r4s5t6u7v8"
down_revision = "p2q3r4s5t6u7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "members",
        sa.Column("signature_url", sa.String(255), nullable=True),
    )
    op.add_column(
        "pt_applications",
        sa.Column("signature_url", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pt_applications", "signature_url")
    op.drop_column("members", "signature_url")
