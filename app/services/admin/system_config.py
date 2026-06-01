"""시스템 운영 설정 서비스 - 단일 행(id=1) 조회·수정.

send_message에서도 매 발송 직전 이 함수로 messaging_enabled 조회.
"""
import logging

from sqlalchemy.orm import Session

from app.models.admin.system_config import SystemConfig
from app.schemas.admin.system_config import SystemConfigUpdate

logger = logging.getLogger(__name__)


def get_system_config(db: Session) -> SystemConfig:
    """단일 행 조회 - 없으면 디폴트 INSERT(messaging_enabled=false)"""
    cfg = db.query(SystemConfig).filter(SystemConfig.id == 1).first()
    if cfg is None:
        # 안전 디폴트 - 메시지 차단 상태로 시작
        cfg = SystemConfig(id=1, messaging_enabled=False)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
        logger.info("SystemConfig 디폴트 행 생성 - messaging_enabled=false")
    return cfg


def is_messaging_enabled(db: Session) -> bool:
    """send_message에서 매 발송 직전 호출 - DB 토글 그대로 반영"""
    return get_system_config(db).messaging_enabled


def update_system_config(
    db: Session, data: SystemConfigUpdate,
) -> SystemConfig:
    """SUPER_ADMIN이 토글 변경 - 즉시 반영"""
    cfg = get_system_config(db)
    if data.messaging_enabled is not None:
        cfg.messaging_enabled = data.messaging_enabled
    db.commit()
    db.refresh(cfg)
    logger.info(
        "SystemConfig 변경: messaging_enabled=%s",
        cfg.messaging_enabled,
    )
    return cfg
