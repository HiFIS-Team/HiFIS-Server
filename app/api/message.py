from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.message import MessageResponse, MessageSendRequest
from app.services import message as message_service

# Internal - 스케줄러 또는 다른 서비스에서 호출 (인증 없음, 사내용)
router = APIRouter(prefix="/messages", tags=["messages"])

@router.post("/send", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def send_message(payload: MessageSendRequest, db: Session = Depends(get_db)):
    """알림톡 발송 (Internal — 스케줄러 호출용)"""
    return message_service.send_message(db, payload)
