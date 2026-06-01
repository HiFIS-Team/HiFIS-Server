"""트리거별 알림톡 고정 양식 - 두 가지 톤

- 시스템 트리거(예약·등록·홀딩 등): 헤더 + 본문 + 푸터 (지점 정보)
- 안부 트리거(D+N, 만기 안내 등): "○○○님 안녕하세요 :) 지점 발송자 직책 입니다." + 본문 (푸터 없음)
"""
from app.schemas.enums import PERSONAL_TRIGGERS, POSITION_LABELS, Position, TriggerType

# 시스템 트리거 공통 헤더 (B안 통일 인사말)
_HEADER = "{name}님 {branch_name} 입니다!"

# 안부 트리거 공통 헤더 (발송자 자기소개)
_PERSONAL_HEADER = "{name}님 안녕하세요 :) {branch_name} {sender_name} {sender_position} 입니다."

# 트리거별 본문 (헤더/푸터 제외) - 문장·줄바꿈·중복 정리, 사실 정보는 원본 유지
_BODIES: dict[str, str] = {
    TriggerType.RESERVATION_CONFIRM.value: """예약이 정상적으로 접수되었습니다.
변동사항이 있으시면 미리 말씀해 주세요. 예약 변경 도와드리겠습니다.
방문하시면 상세하게 안내해 드리겠습니다. 조심해서 오세요^^

[골든타임 이벤트]
당일 등록 시 10% 할인적용
7일 이내 등록 시 5% 할인적용
이후 등록 시 정상가 적용""",

    TriggerType.RESERVATION_CHECK_1.value: """지난번 상담받으셨던 골든타임 이벤트, 적용 기간이 4일 남았어요.
혹시 등록 아직 고민 중이신가요?🙂""",

    TriggerType.RESERVATION_CHECK_2.value: """지난번 상담받으셨던 골든타임 이벤트, 내일이 마감일이에요.
마감 후에는 정상가로만 등록 가능합니다.
혹시 등록 아직 고민 중이신가요?🙂""",

    TriggerType.REGISTERED.value: """인생의 모든 순간이 선택의 순간이라고 생각합니다. 저희를 선택해 주셔서 진심으로 감사드립니다.
회원님의 하루 운동이 가족과 함께할 수 있는 시간을 늘려줍니다. 항상 회원님 가정에 행복한 일들만 가득하시길 기원하겠습니다.""",

    TriggerType.RE_REGISTERED.value: """다시 함께해 주셔서 진심으로 감사드립니다.
새로운 한 걸음, 다시 가볍게 시작하실 수 있도록 옆에서 정성껏 도와드리겠습니다.
오늘도 건강하고 행복한 하루 보내세요^^""",

    TriggerType.D_PLUS_7.value: """축하드려요! 새로운 결심을 하신 지 벌써 일주일이 지났어요.
운동은 처음 한 달이 가장 중요합니다. 도와드릴 일이 있으면 언제든 편하게 연락 주세요.
오늘도 행복한 하루 보내세요^^""",

    TriggerType.D_PLUS_14.value: """대단하세요! 벌써 2주차예요!
이용하시면서 불편하거나 도와드릴 일이 있으면 언제든 편하게 연락 주세요.
오늘도 행복한 하루 보내세요^^""",

    TriggerType.D_PLUS_30.value: """벌써 한 달이 지났어요. 한 달이 모여 일 년이 됩니다.
지금처럼 꾸준히 건강한 하루 보내실 수 있도록 피트니스스타가 최선을 다해 돕겠습니다.
오늘도 행복한 하루 보내세요^^""",

    TriggerType.EXPIRY_SOON_5.value: """이용 기간이 얼마 남지 않아 [리스타트 이벤트] 안내드립니다.
혜택 기간 내에 방문하시는 걸 권장드려요.

[리스타트 이벤트]
만료 전 재등록 시 10% 할인
만료 후 당월 재등록 시 5% 할인
만료 후 익월 재등록 시 정상가""",

    TriggerType.EXPIRY_SOON_2.value: """[리스타트 이벤트] 혜택 기간이 내일까지여서 다시 안내드립니다.
기간이 종료되면 할인율이 줄어듭니다.
방문 일정 알려주시면 친절히 안내 도와드리겠습니다.

[리스타트 이벤트]
만료 전 재등록 시 10% 할인
만료 후 당월 재등록 시 5% 할인
만료 후 익월 재등록 시 정상가""",

    TriggerType.EXPIRED_TODAY.value: """[리스타트 이벤트] 2차 혜택 기간이 이번 달까지여서 다시 안내드립니다.
기간이 종료되면 정상가로만 등록 가능합니다.
방문 일정 알려주시면 친절히 안내 도와드리겠습니다.

[리스타트 이벤트]
만료 후 당월 재등록 시 5% 할인
만료 후 익월 재등록 시 정상가""",

    TriggerType.EXPIRED_FOLLOWUP.value: """운동은 쉬는 기간이 길어질수록 다시 시작하기 더 어려워집니다.
패턴을 잃기 전에, 무리 없이 리듬을 되찾으실 수 있도록 도와드리겠습니다.
언제든 편하게 연락 주세요🙂

[회복 리턴 패키지]
문자 수신 후 5일 이내 등록 시 10% 할인
리턴 건강체크 서비스 (스케줄 예약제)""",
}

def _build_footer(
    branch_name: str, branch_phone: str, naver_place_url: str | None
) -> str:
    """지점별 푸터 생성 - 네이버 링크는 있을 때만 표시 (카카오는 추후 추가 예정)"""
    lines = [
        f"🚩{branch_name}",
        "[상담문의]",
        f"📞{branch_phone}",
    ]
    if naver_place_url:
        lines.append("[네이버 플레이스]")
        lines.append(naver_place_url)
    return "\n".join(lines)

def render_message(
    trigger: str,
    name: str,
    branch_name: str,
    branch_phone: str,
    naver_place_url: str | None = None,
    body_override: str | None = None,
    sender_name: str | None = None,
    sender_position: str | None = None,
) -> str:
    """트리거 양식에 이름·지점정보 치환.

    - 안부 트리거 + sender 정보 있음 → "○○○님 안녕하세요 :) 지점 이름 직책 입니다." + 본문 (푸터 없음)
    - 그 외 (시스템 트리거이거나 sender 정보 없음) → 헤더 + 본문 + 푸터
    - body_override 있으면 트리거 본문 대신 사용 (홀딩 AI 본문 케이스)
    """
    body = body_override or _BODIES.get(trigger, "안녕하세요, 반갑습니다 :)")

    is_personal = (
        trigger in {t.value for t in PERSONAL_TRIGGERS}
        and sender_name and sender_position
    )
    if is_personal:
        # 직책 라벨 변환 (TEAM_LEADER → 팀장 등). 매핑 못 찾으면 코드 그대로.
        try:
            position_label = POSITION_LABELS[Position(sender_position)]
        except (ValueError, KeyError):
            position_label = sender_position
        header = _PERSONAL_HEADER.format(
            name=name,
            branch_name=branch_name,
            sender_name=sender_name,
            sender_position=position_label,
        )
        return f"{header}\n\n{body}"

    header = _HEADER.replace("{name}", name).replace("{branch_name}", branch_name)
    footer = _build_footer(branch_name, branch_phone, naver_place_url)
    return f"{header}\n\n{body}\n\n{footer}"
