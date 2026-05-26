"""홀딩 생성/취소 통합 테스트 - 만기일 연장 + 환불 일수 계산"""
from datetime import date, timedelta

import pytest

from app.models.hold import Hold
from app.models.passes.membership import MembershipPass
from app.models.registrations.member import Member


@pytest.fixture
def registered_member(db, branch):
    """회원권 + 회원 (만기 60일 후) 셋업"""
    pass_ = MembershipPass(
        branch_id=branch.id, name="2개월",
        cash_price=180000, card_price=200000,
    )
    db.add(pass_); db.commit(); db.refresh(pass_)

    today = date.today()
    member = Member(
        branch_id=branch.id, membership_pass_id=pass_.id,
        name="홀딩테스트", gender="M", birth_date="1990-01-01",
        phone="01099998888", address="광주",
        referral="NAVER", payment_method="CARD", final_price=200000,
        start_date=today, end_date=today + timedelta(days=60),
        motivation="HEALTH_IMPROVEMENT", agreed_terms=True,
    )
    db.add(member); db.commit(); db.refresh(member)
    return member


class TestCreateHold:

    def test_create_hold_extends_end_date(
        self, client, db, auth_super, registered_member,
    ):
        """홀딩 생성 → 회원 만기일이 홀딩 일수만큼 연장됨"""
        today = date.today()
        original_end = registered_member.end_date
        hold_days = 10

        res = client.post(
            "/admin/holds",
            headers=auth_super,
            json={
                "source_type": "MEMBER",
                "source_id": str(registered_member.id),
                "reason": "출장",
                "start_date": str(today),
                "end_date": str(today + timedelta(days=hold_days)),
            },
        )
        assert res.status_code in (200, 201), res.text

        # 만기일 연장 확인
        db.refresh(registered_member)
        assert registered_member.end_date == original_end + timedelta(days=hold_days)

        # 홀딩 row 저장 확인
        hold = db.query(Hold).filter(Hold.source_id == registered_member.id).first()
        assert hold is not None
        assert hold.reason == "출장"


class TestCancelHold:

    def test_cancel_hold_immediately_full_refund(
        self, client, db, auth_super, registered_member,
    ):
        """홀딩 생성 직후(같은 날) 취소 → 환불 일수 = 전체, 만기일은 원복"""
        today = date.today()
        original_end = registered_member.end_date
        hold_days = 10

        # 1. 홀딩 생성 (10일 연장됨)
        create_res = client.post(
            "/admin/holds",
            headers=auth_super,
            json={
                "source_type": "MEMBER",
                "source_id": str(registered_member.id),
                "reason": "출장",
                "start_date": str(today),
                "end_date": str(today + timedelta(days=hold_days)),
            },
        )
        assert create_res.status_code in (200, 201)
        hold_id = create_res.json()["id"]

        # 2. 즉시 취소 (today == start_date → 실제 0일 쉼, 10일 환원)
        cancel_res = client.delete(
            f"/admin/holds/{hold_id}",
            headers=auth_super,
        )
        assert cancel_res.status_code in (200, 204), cancel_res.text

        # 만기일이 원래대로 돌아왔는지
        db.refresh(registered_member)
        assert registered_member.end_date == original_end

        # 홀딩 레코드 삭제됨
        assert db.query(Hold).filter(Hold.id == hold_id).first() is None

    def test_cancel_hold_after_end_no_refund(
        self, client, db, auth_super, registered_member, monkeypatch,
    ):
        """홀딩 종료일 지난 뒤 취소 → 환불 0, 만기일 그대로 (이미 다 쉼)

        scenario: 어제 끝난 5일짜리 홀딩을 오늘 취소
        """
        today = date.today()
        hold_start = today - timedelta(days=6)
        hold_end = today - timedelta(days=1)  # 어제 종료
        hold_days = (hold_end - hold_start).days  # 5일

        # 회원 만기일을 미리 연장된 상태로 설정 (홀딩이 이미 적용되어 있다고 가정)
        registered_member.end_date = registered_member.end_date + timedelta(days=hold_days)
        db.commit()
        extended_end = registered_member.end_date

        # 홀딩 레코드 직접 생성 (이미 종료된 과거 홀딩 상황)
        hold = Hold(
            source_type="MEMBER",
            source_id=registered_member.id,
            reason="여행",
            start_date=hold_start,
            end_date=hold_end,
        )
        db.add(hold); db.commit(); db.refresh(hold)

        # 취소
        res = client.delete(f"/admin/holds/{hold.id}", headers=auth_super)
        assert res.status_code in (200, 204), res.text

        # 만기일 변화 없음 (5일 다 쉼 → 환원 0일)
        db.refresh(registered_member)
        assert registered_member.end_date == extended_end


class TestHoldStatusTransitions:
    """HELD 자동 전환 - hold 생성·취소·스케줄러 정리 시 status 변화"""

    def test_create_hold_sets_status_to_held(
        self, client, db, auth_super, registered_member,
    ):
        """홀딩 생성 → 회원 status가 HELD로 자동 전환"""
        today = date.today()
        res = client.post(
            "/admin/holds",
            headers=auth_super,
            json={
                "source_type": "MEMBER",
                "source_id": str(registered_member.id),
                "reason": "출장",
                "start_date": str(today),
                "end_date": str(today + timedelta(days=5)),
            },
        )
        assert res.status_code in (200, 201)
        db.refresh(registered_member)
        assert registered_member.status == "HELD"

    def test_cancel_hold_recalcs_to_registered(
        self, client, db, auth_super, registered_member,
    ):
        """홀딩 즉시 취소 → end_date 미래라 REGISTERED 복귀"""
        today = date.today()
        create_res = client.post(
            "/admin/holds",
            headers=auth_super,
            json={
                "source_type": "MEMBER",
                "source_id": str(registered_member.id),
                "reason": "출장",
                "start_date": str(today),
                "end_date": str(today + timedelta(days=5)),
            },
        )
        hold_id = create_res.json()["id"]
        db.refresh(registered_member)
        assert registered_member.status == "HELD"

        cancel_res = client.delete(
            f"/admin/holds/{hold_id}", headers=auth_super,
        )
        assert cancel_res.status_code in (200, 204)
        db.refresh(registered_member)
        # 즉시 취소 → end_date 원복(60일 후) → REGISTERED
        assert registered_member.status == "REGISTERED"

    def test_scheduler_cleanup_recalcs_status(self, db, registered_member):
        """스케줄러가 만료 홀딩 정리 시 HELD → REGISTERED 복귀"""
        from app.services.messaging.scheduler import _process_expired_holds

        today = date.today()
        # 어제 종료된 hold를 직접 생성 + 회원을 HELD 상태로 (정리 미완 시뮬레이션)
        hold = Hold(
            source_type="MEMBER",
            source_id=registered_member.id,
            reason="과거 홀딩",
            start_date=today - timedelta(days=5),
            end_date=today - timedelta(days=1),
        )
        db.add(hold)
        registered_member.status = "HELD"
        db.commit()

        _process_expired_holds(db, today)

        db.refresh(registered_member)
        assert db.query(Hold).filter(Hold.id == hold.id).first() is None
        # end_date(60일 후) 미래 → REGISTERED
        assert registered_member.status == "REGISTERED"

    def test_multiple_holds_status_stays_held_after_one_cancel(
        self, client, db, auth_super, registered_member,
    ):
        """2개 hold 중 1개만 취소 → 남은 hold 때문에 status는 HELD 유지"""
        today = date.today()
        # 2개의 hold 생성
        r1 = client.post(
            "/admin/holds",
            headers=auth_super,
            json={
                "source_type": "MEMBER",
                "source_id": str(registered_member.id),
                "reason": "출장 1",
                "start_date": str(today),
                "end_date": str(today + timedelta(days=3)),
            },
        )
        hold1_id = r1.json()["id"]
        client.post(
            "/admin/holds",
            headers=auth_super,
            json={
                "source_type": "MEMBER",
                "source_id": str(registered_member.id),
                "reason": "출장 2",
                "start_date": str(today + timedelta(days=4)),
                "end_date": str(today + timedelta(days=8)),
            },
        )

        # 첫 번째만 취소
        client.delete(f"/admin/holds/{hold1_id}", headers=auth_super)
        db.refresh(registered_member)
        # 두 번째 hold가 남아 있으므로 여전히 HELD
        assert registered_member.status == "HELD"


class TestCancelHoldBySource:
    """POST /admin/holds/cancel - source 기반 일괄 취소"""

    def test_cancel_by_source_finds_and_cancels(
        self, client, db, auth_super, registered_member,
    ):
        """source_type/source_id로 활성 hold 찾아서 취소 + status 복귀"""
        today = date.today()
        client.post(
            "/admin/holds",
            headers=auth_super,
            json={
                "source_type": "MEMBER",
                "source_id": str(registered_member.id),
                "reason": "출장",
                "start_date": str(today),
                "end_date": str(today + timedelta(days=5)),
            },
        )

        res = client.post(
            "/admin/holds/cancel",
            headers=auth_super,
            json={
                "source_type": "MEMBER",
                "source_id": str(registered_member.id),
            },
        )
        assert res.status_code == 204, res.text
        db.refresh(registered_member)
        assert registered_member.status == "REGISTERED"
        # 모든 hold 삭제됨
        assert db.query(Hold).filter(
            Hold.source_id == registered_member.id
        ).count() == 0

    def test_cancel_by_source_no_active_hold_404(
        self, client, auth_super, registered_member,
    ):
        """활성 hold 없으면 404"""
        res = client.post(
            "/admin/holds/cancel",
            headers=auth_super,
            json={
                "source_type": "MEMBER",
                "source_id": str(registered_member.id),
            },
        )
        assert res.status_code == 404

    def test_cancel_by_source_reservation_rejected(self, client, auth_super):
        """RESERVATION 타입은 스키마에서 차단"""
        from uuid import uuid4

        res = client.post(
            "/admin/holds/cancel",
            headers=auth_super,
            json={
                "source_type": "RESERVATION",
                "source_id": str(uuid4()),
            },
        )
        assert res.status_code == 422
