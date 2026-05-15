"""트리거별 알림톡 고정 양식 - 이름·지점정보 치환 (B안: 통일 헤더)"""
from app.schemas.enums import TriggerType

# 모든 양식 공통 헤더 (B안 통일 인사말)
_HEADER = "{name}님 {branch_name} 입니다!"

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

    TriggerType.EVENT.value: """(리뉴얼 이벤트) 안내드립니다.
4월 한정 선착순 이벤트로, 단 1개월만 등록하셔도 4만원!
따뜻한 봄날, 가볍게 건강관리 시작해 보세요.

[바른 봄날 패키지]
개월 수 상관없이 4만원 등록 가능
시작일 자유롭게 설정 가능
일일 무제한 입장 가능
담당 트레이너 배정 + PT 1회""",
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
) -> str:
    """트리거 양식에 이름·지점정보 치환 - body_override 있으면 본문으로 사용 (홀딩 등 AI 생성)"""
    body = body_override or _BODIES.get(trigger, "안녕하세요, 반갑습니다 :)")
    header = _HEADER.replace("{name}", name).replace("{branch_name}", branch_name)
    footer = _build_footer(branch_name, branch_phone, naver_place_url)
    return f"{header}\n\n{body}\n\n{footer}"

