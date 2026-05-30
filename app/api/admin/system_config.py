"""시스템 운영 토글 라우터 (SUPER_ADMIN 전용).

GET /admin/system-config - 현재 상태 조회
PATCH /admin/system-config - 토글 변경 (messaging_enabled 등)
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_super_admin
from app.db.deps import get_db
from app.models.admin.admin import Admin
from app.schemas.admin.system_config import (
    SystemConfigResponse,
    SystemConfigUpdate,
)
from app.services.admin import system_config as system_config_service


router = APIRouter(prefix="/admin/system-config", tags=["admin-system-config"])


@router.get("", response_model=SystemConfigResponse)
def get_config(
    db: Session = Depends(get_db),
    _: Admin = Depends(require_super_admin),
):
    """시스템 운영 설정 조회 (SUPER_ADMIN)"""
    return system_config_service.get_system_config(db)


@router.patch("", response_model=SystemConfigResponse)
def update_config(
    payload: SystemConfigUpdate,
    db: Session = Depends(get_db),
    _: Admin = Depends(require_super_admin),
):
    """시스템 운영 설정 변경 (SUPER_ADMIN, 즉시 반영).

    예: messaging_enabled 토글 → 다음 신청부터 적용 (컨테이너 재시작 불필요)
    """
    return system_config_service.update_system_config(db, payload)
