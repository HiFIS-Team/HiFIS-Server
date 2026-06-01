"""회귀 테스트 — production SessionLocal(autoflush=False)에서 hold 취소 시
status가 정상 REGISTERED로 재계산되는지 검증.

배경: 기존 conftest의 `db` fixture는 `Session(bind=connection)` 직접 생성이라
SQLAlchemy 기본인 autoflush=True. 그러나 production의 `SessionLocal`은 autoflush=False.
이 차이로 `_recalc_source_status` 안의 `db.query(Hold)`가 pending delete를 못 보고
status를 HELD로 굳히는 버그가 있었음 (v0.13.0 발견·수정). 같은 패턴을 또
빠뜨리지 않게 prod 세션 모사로 별도 검증.
"""
from datetime import date, timedelta

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.admin.admin import Admin
from app.models.branch import Branch
from app.models.hold import Hold
from app.models.passes.membership import MembershipPass
from app.models.registrations.member import Member
from app.schemas.enums import MessageSourceType
from app.schemas.hold import HoldCreate
from app.services import hold as hold_service


@pytest.fixture
def db_no_autoflush(engine):
    """production SessionLocal(autoflush=False)과 동일 설정.

    트랜잭션 rollback 격리 패턴은 conftest의 `db` fixture와 동일.
    conftest의 `branch`/`super_admin` 등은 다른 connection이라 cross-visible하지
    않으므로, 이 세션을 쓰는 테스트는 자체적으로 셋업해야 한다.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, autoflush=False)
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


def _setup_member_with_hold(db: Session, days_to_expire: int = 60):
    """동일 connection에서 branch + admin + pass + member 풀세트 생성."""
    branch = Branch(name="회귀테스트", phone="050-0000")
    db.add(branch); db.commit(); db.refresh(branch)

    super_admin = Admin(
        email="regression@test.com",
        password_hash=hash_password("test1234"),
        name="회귀admin",
        role="SUPER_ADMIN",
        branch_id=None,
    )
    db.add(super_admin); db.commit(); db.refresh(super_admin)

    pass_ = MembershipPass(
        branch_id=branch.id, name="1개월", cash_price=1, card_price=1,
    )
    db.add(pass_); db.commit(); db.refresh(pass_)

    today = date.today()
    member = Member(
        branch_id=branch.id, membership_pass_id=pass_.id,
        name="autoflush_regression", gender="M", birth_date="1990-01-01",
        phone="01000099001", address="x",
        referral="NAVER", payment_method="CARD", final_price=1,
        start_date=today, end_date=today + timedelta(days=days_to_expire),
        motivation="WEIGHT_LOSS", agreed_terms=True,
    )
    db.add(member); db.commit(); db.refresh(member)
    return branch, super_admin, member


def test_cancel_hold_by_source_recalcs_status_with_autoflush_disabled(
    db_no_autoflush,
):
    """autoflush=False 환경에서도 source 기반 취소 후 status=REGISTERED 복귀.

    수정 전(`_recalc_source_status`에 `db.flush()` 빠짐) 이 테스트는 실패하고
    `member.status == 'HELD'` 로 남는다. fix 후 정상 통과.
    """
    db = db_no_autoflush
    branch, super_admin, member = _setup_member_with_hold(db)
    today = date.today()

    hold_service.create_hold(
        db,
        HoldCreate(
            source_type=MessageSourceType.MEMBER,
            source_id=member.id,
            reason="regression",
            start_date=today,
            end_date=today + timedelta(days=5),
        ),
        super_admin,
    )
    db.refresh(member)
    assert member.status == "HELD"

    hold_service.cancel_hold_by_source(
        db, MessageSourceType.MEMBER, member.id, super_admin,
    )
    db.refresh(member)

    assert member.status == "REGISTERED", (
        f"autoflush=False 환경에서 status 재계산 실패: {member.status} "
        "(서비스에서 db.flush() 빠진 경우 HELD로 굳음)"
    )
    assert db.query(Hold).filter(Hold.source_id == member.id).count() == 0


def test_cancel_hold_by_id_recalcs_status_with_autoflush_disabled(
    db_no_autoflush,
):
    """단일 hold_id 기반 취소도 동일 보장 — `cancel_hold` 경로 회귀 방지."""
    db = db_no_autoflush
    branch, super_admin, member = _setup_member_with_hold(db)
    today = date.today()

    hold = hold_service.create_hold(
        db,
        HoldCreate(
            source_type=MessageSourceType.MEMBER,
            source_id=member.id,
            reason="regression-byid",
            start_date=today,
            end_date=today + timedelta(days=5),
        ),
        super_admin,
    )
    db.refresh(member)
    assert member.status == "HELD"

    hold_service.cancel_hold(db, hold.id, super_admin)
    db.refresh(member)

    assert member.status == "REGISTERED"
    assert db.query(Hold).filter(Hold.source_id == member.id).count() == 0
