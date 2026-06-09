"""alimtalk_templates에 body 컬럼 추가 + 코드 _BODIES seed

Revision ID: t6u7v8w9x0y1
Revises: s5t6u7v8w9x0
Create Date: 2026-06-09

Phase 2 - 트리거별 본문을 DB로 옮김.
- body TEXT NULL 컬럼 추가
- 기존 코드 _BODIES (services/messaging/message_templates.py)의 트리거별
  본문을 그대로 seed → 운영 즉시 동일 메시지 발송.

새 트리거 추가될 땐 코드 _BODIES + 별도 마이그(INSERT 또는 UPDATE)로 동기.
"""
from alembic import op
import sqlalchemy as sa


revision = "t6u7v8w9x0y1"
down_revision = "s5t6u7v8w9x0"
branch_labels = None
depends_on = None


# 코드 _BODIES와 동기 - 변경 시 services/messaging/message_templates.py도 함께.
# 마이그 작성 시점 스냅샷이라, 코드와 어긋나도 폴백(_BODIES)이 안전망.
_BODY_SEED = {
    "RESERVATION_CONFIRM": """예약이 정상적으로 접수되었습니다.
변동사항이 있으시면 미리 말씀해 주세요. 예약 변경 도와드리겠습니다.
방문하시면 상세하게 안내해 드리겠습니다. 조심해서 오세요^^

[골든타임 이벤트]
당일 등록 시 10% 할인적용
7일 이내 등록 시 5% 할인적용
이후 등록 시 정상가 적용""",

    "RESERVATION_CHECK_1": """지난번 상담받으셨던 골든타임 이벤트, 적용 기간이 4일 남았어요.
혹시 등록 아직 고민 중이신가요?🙂""",

    "RESERVATION_CHECK_2": """지난번 상담받으셨던 골든타임 이벤트, 내일이 마감일이에요.
마감 후에는 정상가로만 등록 가능합니다.
혹시 등록 아직 고민 중이신가요?🙂""",

    "REGISTERED": """인생의 모든 순간이 선택의 순간이라고 생각합니다. 저희를 선택해 주셔서 진심으로 감사드립니다.
회원님의 하루 운동이 가족과 함께할 수 있는 시간을 늘려줍니다. 항상 회원님 가정에 행복한 일들만 가득하시길 기원하겠습니다.""",

    "RE_REGISTERED": """다시 함께해 주셔서 진심으로 감사드립니다.
새로운 한 걸음, 다시 가볍게 시작하실 수 있도록 옆에서 정성껏 도와드리겠습니다.
오늘도 건강하고 행복한 하루 보내세요^^""",

    "D_PLUS_7": """축하드려요! 새로운 결심을 하신 지 벌써 일주일이 지났어요.
운동은 처음 한 달이 가장 중요합니다. 도와드릴 일이 있으면 언제든 편하게 연락 주세요.
오늘도 행복한 하루 보내세요^^""",

    "D_PLUS_14": """대단하세요! 벌써 2주차예요!
이용하시면서 불편하거나 도와드릴 일이 있으면 언제든 편하게 연락 주세요.
오늘도 행복한 하루 보내세요^^""",

    "D_PLUS_30": """벌써 한 달이 지났어요. 한 달이 모여 일 년이 됩니다.
지금처럼 꾸준히 건강한 하루 보내실 수 있도록 피트니스스타가 최선을 다해 돕겠습니다.
오늘도 행복한 하루 보내세요^^""",

    "EXPIRY_SOON_5": """이용 기간이 얼마 남지 않아 [리스타트 이벤트] 안내드립니다.
혜택 기간 내에 방문하시는 걸 권장드려요.

[리스타트 이벤트]
만료 전 재등록 시 10% 할인
만료 후 당월 재등록 시 5% 할인
만료 후 익월 재등록 시 정상가""",

    "EXPIRY_SOON_2": """[리스타트 이벤트] 혜택 기간이 내일까지여서 다시 안내드립니다.
기간이 종료되면 할인율이 줄어듭니다.
방문 일정 알려주시면 친절히 안내 도와드리겠습니다.

[리스타트 이벤트]
만료 전 재등록 시 10% 할인
만료 후 당월 재등록 시 5% 할인
만료 후 익월 재등록 시 정상가""",

    "EXPIRED_TODAY": """[리스타트 이벤트] 2차 혜택 기간이 이번 달까지여서 다시 안내드립니다.
기간이 종료되면 정상가로만 등록 가능합니다.
방문 일정 알려주시면 친절히 안내 도와드리겠습니다.

[리스타트 이벤트]
만료 후 당월 재등록 시 5% 할인
만료 후 익월 재등록 시 정상가""",

    "EXPIRED_FOLLOWUP": """운동은 쉬는 기간이 길어질수록 다시 시작하기 더 어려워집니다.
패턴을 잃기 전에, 무리 없이 리듬을 되찾으실 수 있도록 도와드리겠습니다.
언제든 편하게 연락 주세요🙂

[회복 리턴 패키지]
문자 수신 후 5일 이내 등록 시 10% 할인
리턴 건강체크 서비스 (스케줄 예약제)""",
}


def upgrade() -> None:
    op.add_column(
        "alimtalk_templates",
        sa.Column("body", sa.Text(), nullable=True),
    )
    # 트리거별 본문 seed - %L 포맷으로 SQL 리터럴 안전 처리
    bind = op.get_bind()
    for trigger, body in _BODY_SEED.items():
        bind.execute(
            sa.text(
                "UPDATE alimtalk_templates SET body = :body "
                "WHERE trigger_type = :trigger_type"
            ),
            {"body": body, "trigger_type": trigger},
        )


def downgrade() -> None:
    op.drop_column("alimtalk_templates", "body")
