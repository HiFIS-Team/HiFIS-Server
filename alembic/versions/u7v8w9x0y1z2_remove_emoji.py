"""alimtalk_templates body에서 이모지 제거 (LMS 깨짐 대응)

Revision ID: u7v8w9x0y1z2
Revises: t6u7v8w9x0y1
Create Date: 2026-06-10

LMS에서 이모지가 깨져 보여 본문에서 제거.
- RESERVATION_CHECK_1, RESERVATION_CHECK_2, EXPIRED_FOLLOWUP 본문 끝의 🙂 삭제
- 푸터는 코드 _FOOTER_TEMPLATE / _build_footer 에서 별도 처리 (DB 무관)

이미 사장님이 본문 편집해서 DB body가 코드 _BODIES와 다르면 건드리지 않음
(REPLACE 사용 - 옛 패턴이 정확히 있을 때만 치환).
"""
from alembic import op
import sqlalchemy as sa


revision = "u7v8w9x0y1z2"
down_revision = "t6u7v8w9x0y1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # 본문 끝의 "🙂" 제거 - REPLACE는 패턴 없으면 무동작이라 안전
    bind.execute(sa.text(
        "UPDATE alimtalk_templates SET body = REPLACE(body, '🙂', '') "
        "WHERE body LIKE '%🙂%'"
    ))


def downgrade() -> None:
    # 복원 어려움 (어디에 🙂 박혀있었는지 모름) - 수동 복원 권장
    pass
