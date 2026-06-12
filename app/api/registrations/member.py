from uuid import UUID
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.rate_limit import limiter
from app.models.admin.admin import Admin
from app.db.deps import get_db
from app.schemas.common import Page
from app.schemas.registrations.member import (
    MemberCreate,
    MemberReRegister,
    MemberResponse,
    MemberUpdate,
)
from app.schemas.enums import MemberStatus
from app.services.registrations import member as member_service
from app.services.storage import MAX_SIGNATURE_BYTES, save_signature
from app.utils.image import ImageValidationError, ensure_jpeg
from pydantic import ValidationError

# 얼굴 사진 - 정규화 전 원본 10MB 제한 (iPhone 고해상도 대비)
MAX_FACE_BYTES = 10 * 1024 * 1024

# Public - 회원가입 신청서 제출 (인증 불필요)
public_router = APIRouter(prefix="/members", tags=["members"])


async def _parse_member_payload(
    request: Request, schema_cls,
) -> tuple[object, str | None, bytes | None]:
    """JSON / multipart 둘 다 받아서 (스키마 인스턴스, signature_url, face_jpeg) 반환.

    - application/json: 기존 흐름. signature·face 둘 다 None.
    - multipart/form-data:
        payload (필수): MemberCreate JSON 문자열
        signature (선택): PNG, 1MB 이하 - 디스크 저장 → URL 반환
        face_image (선택): JPEG/PNG, 10MB 이하 - Pillow로 정규화한 JPEG 바이트 반환
    """
    ct = request.headers.get("content-type", "")
    if ct.startswith("multipart/"):
        form = await request.form()
        payload_str = form.get("payload")
        if not isinstance(payload_str, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="multipart 요청은 payload(JSON 문자열) 필드가 필요합니다.",
            )
        try:
            data = schema_cls.model_validate_json(payload_str)
        except ValidationError as e:
            raise HTTPException(
                status_code=422,
                detail=e.errors(include_context=False, include_url=False),
            ) from e

        signature_url: str | None = None
        signature = form.get("signature")
        if signature is not None and hasattr(signature, "read"):
            if signature.content_type and signature.content_type != "image/png":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"서명은 PNG만 허용됩니다: {signature.content_type}",
                )
            sig_bytes = await signature.read()
            if len(sig_bytes) > MAX_SIGNATURE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="서명 크기 초과 (최대 1MB)",
                )
            signature_url = save_signature(sig_bytes)

        face_jpeg: bytes | None = None
        face = form.get("face_image")
        if face is not None and hasattr(face, "read"):
            face_bytes = await face.read()
            if len(face_bytes) > MAX_FACE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="얼굴 사진 크기 초과 (최대 10MB)",
                )
            try:
                face_jpeg = ensure_jpeg(face_bytes)
            except ImageValidationError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e),
                ) from e
        return data, signature_url, face_jpeg

    body = await request.json()
    try:
        return schema_cls.model_validate(body), None, None
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=e.errors(include_context=False, include_url=False),
        ) from e


@public_router.post("", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_member(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """회원가입 신청 (Public). JSON / multipart(payload + signature) 둘 다 지원.

    어드민 알림은 BackgroundTasks로 응답 후 발송.
    """
    data, signature_url, face_jpeg = await _parse_member_payload(
        request, MemberCreate,
    )
    return member_service.create_member(
        db, data, background_tasks,
        signature_url=signature_url,
        face_jpeg=face_jpeg,
    )


@public_router.post("/re-register", response_model=MemberResponse)
@limiter.limit("30/minute")
async def re_register_member(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """재등록 신청 (Public) - 기존 회원의 회원권 갱신 + final_price 누적.

    JSON / multipart 둘 다 지원. 식별: branch_id + name + phone 일치.
    없으면 404, 둘 이상이면 400. 옛 행 UPDATE 후 RE_REGISTERED 알림톡 발송.
    """
    # 재등록은 얼굴 인증 다시 안 받음 - 이미 다짐에 등록된 회원이라 face_jpeg 무시
    data, signature_url, _face = await _parse_member_payload(
        request, MemberReRegister,
    )
    return member_service.re_register_member(
        db, data, background_tasks, signature_url=signature_url,
    )

# Admin - 인증 의존성은 인증 도입 후 부착
admin_router = APIRouter(prefix="/admin/members", tags=["admin-members"])

@admin_router.get("", response_model=Page[MemberResponse])
def admin_list_members(
    branch_id: UUID | None = None,
    name: str | None = None,
    phone: str | None = None,
    status: MemberStatus | None = None,
    start_date_from: date | None = None,
    start_date_to: date | None = None,
    end_date_from: date | None = None,
    end_date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """회원 목록 조회 + 페이지네이션 (Admin, FC는 자기 지점만) - 필터·페이지·페이지사이즈

    전체 카운트·차트·상태분포 등 집계는 GET /admin/dashboard/summary 사용.
    """
    items, total = member_service.list_members(
        db, branch_id, name, phone, status,
        start_date_from, start_date_to,
        end_date_from, end_date_to,
        current_admin, page, page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@admin_router.get("/{member_id}", response_model=MemberResponse)
def admin_get_member(
    member_id: UUID, 
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """회원 상태 조회 (Admin)"""
    return member_service.get_member(db, member_id, current_admin)

@admin_router.patch("/{member_id}", response_model=MemberResponse)
def admin_update_member(
    member_id: UUID,
    payload: MemberUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """회원 정보 수정 (Admin, 부분 수정)"""
    return member_service.update_member(db, member_id, payload, current_admin)

@admin_router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_member(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """회원 삭제 (Admin) - FC는 자기 지점만"""
    member_service.delete_member(db, member_id, current_admin)
