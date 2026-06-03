"""branches에 dajim_gym_id 컬럼 추가 - 지점별 다짐 GYM_ID

Revision ID: p2q3r4s5t6u7
Revises: o1p2q3r4s5t6
Create Date: 2026-06-01

다짐 x-gym-id 헤더 값. 첨단점·동광주점 GYM_ID가 다르기 때문에 .env 단일 값 대신
Branch 컬럼으로 분리. dajim_enabled=True인 지점은 이 값 필수 (NULL이면 등록 스킵).

마이그 시 알려진 GYM_ID 자동 INSERT:
- 동광주점: ab413191-70fa-4392-a886-14ac42f2834c
- 첨단점:   64387553-14c3-43c5-988e-cdd9c21e2240
화순점: NULL (브로제이 사용)
"""
from alembic import op
import sqlalchemy as sa


revision = "p2q3r4s5t6u7"
down_revision = "o1p2q3r4s5t6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "branches",
        sa.Column("dajim_gym_id", sa.String(50), nullable=True),
    )
    # 알려진 지점 GYM_ID 박기 (이름 매칭, 없으면 no-op)
    op.execute(
        "UPDATE branches SET dajim_gym_id='ab413191-70fa-4392-a886-14ac42f2834c' "
        "WHERE name='피트니스스타 동광주점'"
    )
    op.execute(
        "UPDATE branches SET dajim_gym_id='64387553-14c3-43c5-988e-cdd9c21e2240' "
        "WHERE name='피트니스스타 첨단점'"
    )


def downgrade() -> None:
    op.drop_column("branches", "dajim_gym_id")
