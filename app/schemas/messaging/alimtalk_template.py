from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AlimtalkVariable(BaseModel):
    """본문에 박을 수 있는 변수 한 개"""
    key: str        # placeholder 키 (예: "name")
    label: str      # 한국어 라벨 (예: "회원 이름")


class AlimtalkTemplateResponse(BaseModel):
    """트리거 토글 + 본문 + 사용 가능 변수 + 헤더/푸터 템플릿"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    trigger_type: str
    is_enabled: bool
    body: str | None     # NULL이면 코드 디폴트 폴백
    default_body: str    # 코드 _BODIES 디폴트 (참고용)
    variables: list[AlimtalkVariable]   # 이 트리거에서 본문에 쓸 수 있는 변수
    # raw 헤더/푸터 템플릿 - placeholder({name}, {branch_name}) 그대로 노출.
    # footer_template은 안부 트리거에선 None (실 발송 시 푸터 없음).
    header_template: str
    footer_template: str | None
    updated_at: datetime


class AlimtalkTemplateUpdate(BaseModel):
    """PATCH 본문 - is_enabled/body 모두 부분 수정 가능"""
    is_enabled: bool | None = None
    body: str | None = None    # 빈 문자열·None 모두 허용 (디폴트 복원)


class AlimtalkTemplatePreviewRequest(BaseModel):
    """미리보기 요청 - 편집 중인 본문과 대표 지점 선택"""
    body: str | None = None     # 미입력 시 DB 저장 본문 또는 코드 디폴트 사용
    branch_id: UUID | None = None   # 미입력 시 첫 지점 사용 (헤더/푸터/발송자 채움)


class AlimtalkTemplatePreviewResponse(BaseModel):
    """미리보기 응답 - 헤더+본문+푸터 전체 조립된 텍스트"""
    preview: str
