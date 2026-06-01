"""매일 자정 자동 트리거 - 알림톡 발송 + 만기 상태 변경 + 가입 잔재 정리"""
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.admin.admin import Admin
from app.models.registrations.member import Member
from app.models.messaging.message import Message
from app.models.hold import Hold
from app.models.registrations.pt_application import PTApplication
from app.models.registrations.reservation import Reservation
from app.schemas.enums import(
    AdminStatus,
    MemberStatus,
    MessageSourceType,
    MessageStatus,
    TriggerType,
)
from app.schemas.messaging.message import MessageSendRequest
from app.services.messaging import message as message_service

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")               
scheduler = BackgroundScheduler(timezone="Asia/Seoul")

def start_scheduler() -> None:
    """앱 시작 시 호출 - 매일 자정 잡 등록"""
    if not scheduler.running:
        scheduler.add_job(
            run_daily_triggers,
            "cron",
            hour=8,
            minute=0,
            id="daily_triggers",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("스케줄러 시작 - 매일 08:00 KST 트리거 등록 완료")

def stop_scheduler() -> None:
    """앱 종료 시 호출"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("스케줄러 종료")

def run_daily_triggers() -> None:
    """매일 오전 8시(KST) 실행 - 모든 트리거 처리"""
    db = SessionLocal()
    try:
        today = date.today()
        logger.info("스케줄러 실행: %s", today)

        # 예약 미등록 권유
        _process_reservation_check(db, today, 3, TriggerType.RESERVATION_CHECK_1)
        _process_reservation_check(db, today, 5, TriggerType.RESERVATION_CHECK_2)
        
        # 회원/PT 신청 D+N
        for days, trigger in [
            (7, TriggerType.D_PLUS_7),
            (14, TriggerType.D_PLUS_14),
            (30, TriggerType.D_PLUS_30),
        ]:
            _process_member_d_plus(db, today, days, trigger)
            _process_pt_d_plus(db, today, days, trigger)
        
        # 만기 임박
        for days, trigger in [
            (5, TriggerType.EXPIRY_SOON_5),
            (2, TriggerType.EXPIRY_SOON_2),
        ]:
            _process_expiry_soon(db, today, days, trigger)

        # 만기 당일 안내 발송 (상태 변경 전에)   ★ 추가된 줄
        _process_expired_today(db, today)         # ★ 추가된 줄
        
        # 만기 도래 -> EXPIRED 변경 (알림 X)
        _process_expire_status(db, today)

        _process_expired_holds(db, today)

        # 만기 +30일 재등록 권유
        _process_expired_followup(db, today, 30, TriggerType.EXPIRED_FOLLOWUP)

        # PENDING_EMAIL 가입 잔재 정리 (24h 지난 미인증 row)
        _cleanup_stale_pending_email_admins(db)

        logger.info("스케줄러 실행 완료")
    except Exception as e:
        logger.exception("스케줄러 실행 중 에러: %s", e)
    finally:
        db.close()

# === 트리거벌 처리 함수 ===

def _process_reservation_check(db: Session, today: date, days: int, trigger: TriggerType,) -> None:
    """에약 +N일에 회원/PT 등록 안 한 사람만 권유 알림"""
    target_date = today - timedelta(days=days)
    reservations = db.query(Reservation).filter(
        func.date(Reservation.created_at) == target_date,
    ).all()

    for r in reservations:
        # 이미 회원 등록한 사람 스킵
        if db.query(Member).filter(Member.phone == r.phone).first():
            continue
        if db.query(PTApplication).filter(PTApplication.phone == r.phone).first():
            continue

        _try_send(
            db,
            branch_id=r.branch_id,
            source_type=MessageSourceType.RESERVATION,
            source_id=r.id,
            trigger=trigger,
            recipient=r.phone,
            name=r.name,
        )

def _process_member_d_plus(db: Session, today: date, days: int, trigger: TriggerType) -> None:
    """회원 created_at +N일 알림"""
    target_date = today - timedelta(days=days)
    members = db.query(Member).filter(
        func.date(Member.created_at) == target_date,
        Member.status == MemberStatus.REGISTERED.value,
    ).all()

    for m in members:
        _try_send(
            db,
            branch_id=m.branch_id,
            source_type=MessageSourceType.MEMBER,
            source_id=m.id,
            trigger=trigger,
            recipient=m.phone,
            name=m.name,
        )

def _process_pt_d_plus(db: Session, today: date, days: int, trigger: TriggerType) -> None:
    """PT 신청 created_at +N일 알림"""
    target_date = today - timedelta(days=days)
    apps = db.query(PTApplication).filter(
        func.date(PTApplication.created_at) == target_date,
        PTApplication.status == MemberStatus.REGISTERED.value,
    ).all()

    for a in apps:
        _try_send(
            db,
            branch_id=a.branch_id,
            source_type=MessageSourceType.PT_APPLICATION,
            source_id=a.id,
            trigger=trigger,
            recipient=a.phone,
            name=a.name,
        )

def _process_expiry_soon(db: Session, today: date, days: int, trigger: TriggerType) -> None:
    """만기 N일 전 알림 (회원/PT)"""
    target_date = today + timedelta(days=days)

    members = db.query(Member).filter(
        Member.end_date == target_date,
        Member.status == MemberStatus.REGISTERED.value,
    ).all()

    for m in members:
        _try_send(
            db,
            branch_id=m.branch_id,
            source_type=MessageSourceType.MEMBER,
            source_id=m.id,
            trigger=trigger,
            recipient=m.phone,
            name=m.name,
        )
    
    apps = db.query(PTApplication).filter(
        PTApplication.end_date == target_date,
        PTApplication.status == MemberStatus.REGISTERED.value,
    ).all()

    for a in apps:
        _try_send(
            db,
            branch_id=a.branch_id,
            source_type=MessageSourceType.PT_APPLICATION,
            source_id=a.id,
            trigger=trigger,
            recipient=a.phone,
            name=a.name,
        )

def _process_expire_status(db: Session, today: date) -> None:
    """end_date 지난 회원/PT를 EXPIRED로 변경 (알림 X)"""
    members = db.query(Member).filter(
        Member.end_date < today,
        Member.status == MemberStatus.REGISTERED.value,
    ).all()

    for m in members:
        m.status = MemberStatus.EXPIRED.value

    apps = db.query(PTApplication).filter(
        PTApplication.end_date < today,
        PTApplication.status == MemberStatus.REGISTERED.value,
    ).all()

    for a in apps:
        a.status = MemberStatus.EXPIRED.value

    db.commit()
    if members or apps:
        logger.info(
            "EXPIRED 상태 변경: members=%d, pt_applications=%d",
            len(members), len(apps),
        )

def _process_expired_followup(
    db: Session, today: date, days: int, trigger: TriggerType,
) -> None:
    """만기 +N일에 재등록 권유 - 마케팅성이라 agreed_marketing=True 만 발송 (법 준수)"""
    target_date = today - timedelta(days=days)

    members = db.query(Member).filter(
        Member.end_date == target_date,
        Member.status == MemberStatus.EXPIRED.value,
        Member.agreed_marketing == True,  # noqa: E712 - SQLAlchemy 필터
    ).all()
    for m in members:
        _try_send(
            db,
            branch_id=m.branch_id,
            source_type=MessageSourceType.MEMBER,
            source_id=m.id,
            trigger=trigger,
            recipient=m.phone,
            name=m.name,
        )

    apps = db.query(PTApplication).filter(
        PTApplication.end_date == target_date,
        PTApplication.status == MemberStatus.EXPIRED.value,
        PTApplication.agreed_marketing == True,  # noqa: E712
    ).all()
    for a in apps:
        _try_send(
            db,
            branch_id=a.branch_id,
            source_type=MessageSourceType.PT_APPLICATION,
            source_id=a.id,
            trigger=trigger,
            recipient=a.phone,
            name=a.name,
        )


def _try_send(
    db, branch_id, source_type, source_id, trigger, recipient, name,
) -> None:
    """발송 헬퍼 - 중복 발송 방지 + 에러 시 로그만 남기고 계속"""
    # 중복 방지
    already = db.query(Message).filter(
        Message.source_id == source_id,
        Message.trigger_type == trigger.value,
        Message.status == MessageStatus.SUCCESS.value,
    ).first()
    if already:
        return

    try:
        message_service.send_message(
            db,
            MessageSendRequest(
                branch_id=branch_id,
                source_type=source_type,
                source_id=source_id,
                trigger_type=trigger,
                recipient=recipient,
                name=name,
            ),
        )
    except Exception as e:
        logger.error(
            "스케줄러 알림 발송 실패: source=%s/%s, trigger=%s, error=%s",
            source_type.value, source_id, trigger.value, str(e),
        )

def _process_expired_today(db: Session, today: date) -> None:
    """만기 당일 회원/PT에게 재등록 안내 (상태 변경은 _process_expire_status가 다음날 처리)"""
    members = db.query(Member).filter(
        Member.end_date == today,
        Member.status == MemberStatus.REGISTERED.value,
    ).all()
    for m in members:
        _try_send(
            db,
            branch_id=m.branch_id,
            source_type=MessageSourceType.MEMBER,
            source_id=m.id,
            trigger=TriggerType.EXPIRED_TODAY,
            recipient=m.phone,
            name=m.name,
        )

    apps = db.query(PTApplication).filter(
        PTApplication.end_date == today,
        PTApplication.status == MemberStatus.REGISTERED.value,
    ).all()
    for a in apps:
        _try_send(
            db,
            branch_id=a.branch_id,
            source_type=MessageSourceType.PT_APPLICATION,
            source_id=a.id,
            trigger=TriggerType.EXPIRED_TODAY,
            recipient=a.phone,
            name=a.name,
        )

def _process_expired_holds(db: Session, today: date) -> None:
    """종료일 지난 홀딩 레코드 자동 정리 + 영향받은 source의 status 재계산 (무음).

    회원 만기일은 이미 정상 연장된 상태. 홀딩이 끝났으니 HELD에 머문 source를
    end_date 기준으로 REGISTERED 또는 EXPIRED로 되돌린다.
    """
    expired = db.query(Hold).filter(Hold.end_date < today).all()
    if not expired:
        return

    # 영향받은 (source_type, source_id) 집합 (중복 제거)
    affected = {(h.source_type, h.source_id) for h in expired}

    for h in expired:
        db.delete(h)
    db.flush()  # 삭제 반영 → 이후 남은 hold 조회가 정확하도록

    for source_type_str, source_id in affected:
        if source_type_str == MessageSourceType.MEMBER.value:
            target = db.query(Member).filter(Member.id == source_id).first()
        elif source_type_str == MessageSourceType.PT_APPLICATION.value:
            target = db.query(PTApplication).filter(
                PTApplication.id == source_id
            ).first()
        else:
            continue
        if target is None:
            continue

        remaining = db.query(Hold).filter(
            Hold.source_type == source_type_str,
            Hold.source_id == source_id,
        ).first()
        if remaining is not None:
            target.status = MemberStatus.HELD.value
        elif today >= target.end_date:
            target.status = MemberStatus.EXPIRED.value
        else:
            target.status = MemberStatus.REGISTERED.value

    db.commit()
    logger.info(
        "홀딩 자동 종료 정리: %d건, 영향 source: %d개",
        len(expired), len(affected),
    )

def _cleanup_stale_pending_email_admins(db: Session) -> None:
    """가입 후 24시간 지났는데 이메일 인증 안 끝낸 PENDING_EMAIL row 정리.

    어드민 관리자 목록에 같은 이메일이 '인증 대기' + '활성' 둘로 보이는 잔재 차단.
    EmailVerificationToken은 admin_id FK CASCADE라 같이 사라짐.
    """
    cutoff = datetime.now(KST) - timedelta(hours=24)
    stale = db.query(Admin).filter(
        Admin.status == AdminStatus.PENDING_EMAIL.value,
        Admin.created_at < cutoff,
    ).all()
    if not stale:
        return
    for admin in stale:
        logger.info(
            "PENDING_EMAIL 24h 만료 cleanup: admin_id=%s, email=%s, created_at=%s",
            admin.id, admin.email, admin.created_at,
        )
        db.delete(admin)
    db.commit()
    logger.info("PENDING_EMAIL 잔재 정리 완료: %d건", len(stale))

