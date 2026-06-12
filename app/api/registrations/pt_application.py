from uuid import UUID
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.rate_limit import limiter
from app.models.admin.admin import Admin
from app.db.deps import get_db
from app.schemas.common import Page
from app.schemas.registrations.pt_application import (
    PTApplicationCreate,
    PTApplicationReRegister,
    PTApplicationResponse,
    PTApplicationUpdate,
)
from app.schemas.enums import MemberStatus
from app.services.registrations import pt_application as pt_application_service
from app.services.storage import MAX_SIGNATURE_BYTES, save_signature
from app.utils.image import ImageValidationError, ensure_jpeg
from pydantic import ValidationError

MAX_FACE_BYTES = 10 * 1024 * 1024

# Public - PT 신청서 제출 (인증 불필요)
public_router = APIRouter(prefix="/pt-applications", tags=["pt-applications"])


async def _parse_pt_payload(
    request: Request, schema_cls,
) -> tuple[object, str | None, bytes | None]:
    """JSON / multipart 둘 다 받아서 (스키마, signature_url, face_jpeg) 반환.

    member 라우터의 _parse_member_payload와 동일 패턴 (signature + face_image).
    Pydantic ValidationError는 422로 변환.
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


@public_router.post("", response_model=PTApplicationResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_pt_application(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """PT 신청서 생성 (Public). JSON / multipart 둘 다 지원."""
    data, signature_url, face_jpeg = await _parse_pt_payload(
        request, PTApplicationCreate,
    )
    return pt_application_service.create_pt_application(
        db, data, background_tasks,
        signature_url=signature_url,
        face_jpeg=face_jpeg,
    )


@public_router.post("/re-register", response_model=PTApplicationResponse)
@limiter.limit("30/minute")
async def re_register_pt_application(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """PT 재등록 신청 (Public) - 기존 PT 행 UPDATE + final_price 누적.

    JSON / multipart 둘 다 지원. 식별: branch_id + name + phone 일치.
    """
    # 재등록은 얼굴 재인증 X (이미 다짐 등록 회원)
    data, signature_url, _face = await _parse_pt_payload(
        request, PTApplicationReRegister,
    )
    return pt_application_service.re_register_pt_application(
        db, data, background_tasks, signature_url=signature_url,
    )

# Admin - 인증 의존성은 인증 도입 후 부착
admin_router = APIRouter(prefix="/admin/pt-applications", tags=["admin-pt-applications"])

@admin_router.get("", response_model=Page[PTApplicationResponse])
def admin_list_pt_application(
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
    """PT 신청 목록 + 페이지네이션 (Admin, FC는 자기 지점만) - 필터·페이지·페이지사이즈

    전체 집계는 GET /admin/dashboard/summary 사용.
    """
    items, total = pt_application_service.list_pt_applications(
        db, branch_id, name, phone, status,
        start_date_from, start_date_to,
        end_date_from, end_date_to,
        current_admin, page, page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}

@admin_router.get("/{application_id}", response_model=PTApplicationResponse)
def admin_get_pt_application(
    application_id: UUID,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """PT 신청 상세 조회 (Admin)"""
    return pt_application_service.get_pt_application(db, application_id, current_admin)

@admin_router.patch("/{application_id}", response_model=PTApplicationResponse)
def admin_update_pt_application(
    application_id: UUID,
    payload: PTApplicationUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """PT 신청 정보 수정 (Admin, 부분 수정)"""
    return pt_application_service.update_pt_application(
        db, application_id, payload, current_admin
    )

@admin_router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_pt_application(
    application_id: UUID,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """PT 신청 삭제 (Admin) - FC는 자기 지점만"""
    pt_application_service.delete_pt_application(db, application_id, current_admin)