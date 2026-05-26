"""GET /admin/dashboard/summary 통합 테스트"""
from datetime import date, timedelta

import pytest

from app.models.passes.membership import MembershipPass
from app.models.passes.pt import PTPass
from app.models.registrations.member import Member
from app.models.registrations.pt_application import PTApplication
from app.models.registrations.reservation import Reservation


def _make_member(
    db, branch, pass_id, name, gender, birth_date_str, phone,
    status="REGISTERED", motivation="WEIGHT_LOSS",
    referral="NAVER", end_offset=30,
):
    today = date.today()
    m = Member(
        branch_id=branch.id, membership_pass_id=pass_id,
        name=name, gender=gender, birth_date=birth_date_str,
        phone=phone, address="광주", referral=referral,
        payment_method="CARD", final_price=1,
        start_date=today, end_date=today + timedelta(days=end_offset),
        motivation=motivation, agreed_terms=True, status=status,
    )
    db.add(m); db.commit(); db.refresh(m)
    return m


class TestDashboardSummary:

    def test_no_auth_401(self, client):
        res = client.get("/admin/dashboard/summary")
        assert res.status_code == 401

    def test_empty_state(self, client, auth_super):
        """데이터 없을 때 — 모든 카운트 0, dict 빈"""
        res = client.get("/admin/dashboard/summary", headers=auth_super)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["members"]["total"] == 0
        assert body["members"]["by_status"] == {}
        assert body["members"]["this_month_signups"] == 0
        assert body["members"]["this_month_by_day"] == []
        assert body["members"]["birthday_today"] == []
        assert body["members"]["expiring_soon_count"] == 0
        assert body["members"]["recent"] == []
        assert body["pt_applications"]["total"] == 0
        assert body["reservations"]["total"] == 0
        assert body["messages"]["total"] == 0

    def test_member_counts_and_by_status(self, client, db, auth_super, branch):
        """회원 total · by_status · by_gender"""
        p = MembershipPass(
            branch_id=branch.id, name="1개월", cash_price=1, card_price=1,
        )
        db.add(p); db.commit(); db.refresh(p)

        _make_member(db, branch, p.id, "활성1", "M", "1990-01-01", "01000000001")
        _make_member(db, branch, p.id, "활성2", "F", "1992-02-02", "01000000002")
        _make_member(
            db, branch, p.id, "만료", "M", "1985-05-05", "01000000003",
            status="EXPIRED",
        )

        res = client.get("/admin/dashboard/summary", headers=auth_super)
        body = res.json()
        assert body["members"]["total"] == 3
        assert body["members"]["by_status"]["REGISTERED"] == 2
        assert body["members"]["by_status"]["EXPIRED"] == 1
        assert body["members"]["by_gender"]["M"] == 2
        assert body["members"]["by_gender"]["F"] == 1

    def test_birthday_today_detected(self, client, db, auth_super, branch):
        """오늘 생일인 회원만 birthday_today에 포함"""
        today = date.today()
        p = MembershipPass(
            branch_id=branch.id, name="1개월", cash_price=1, card_price=1,
        )
        db.add(p); db.commit(); db.refresh(p)

        birthday_str = date(1995, today.month, today.day).isoformat()
        _make_member(db, branch, p.id, "생일자", "F", birthday_str, "01000000001")
        _make_member(db, branch, p.id, "비생일", "M", "1990-01-01", "01000000002")

        res = client.get("/admin/dashboard/summary", headers=auth_super)
        body = res.json()
        birthdays = body["members"]["birthday_today"]
        names = {b["name"] for b in birthdays}
        assert "생일자" in names
        assert "비생일" not in names

    def test_expiring_soon_count(self, client, db, auth_super, branch):
        """end_date가 7일 안에 있는 REGISTERED만 카운트"""
        today = date.today()
        p = MembershipPass(
            branch_id=branch.id, name="1개월", cash_price=1, card_price=1,
        )
        db.add(p); db.commit(); db.refresh(p)

        # 5일 후 만기 → 포함
        _make_member(db, branch, p.id, "임박A", "M", "1990-01-01", "01000000001",
                     end_offset=5)
        # 10일 후 만기 → 제외
        _make_member(db, branch, p.id, "여유", "M", "1990-01-01", "01000000002",
                     end_offset=10)
        # 만료 상태 → 제외
        _make_member(db, branch, p.id, "이미만료", "M", "1990-01-01", "01000000003",
                     status="EXPIRED", end_offset=2)

        res = client.get("/admin/dashboard/summary", headers=auth_super)
        body = res.json()
        assert body["members"]["expiring_soon_count"] == 1

    def test_by_membership_pass_counts_active_only(
        self, client, db, auth_super, branch,
    ):
        """by_membership_pass는 활성(REGISTERED + HELD)만 카운트, EXPIRED 제외"""
        p1 = MembershipPass(
            branch_id=branch.id, name="1개월", cash_price=1, card_price=1,
        )
        p2 = MembershipPass(
            branch_id=branch.id, name="3개월", cash_price=1, card_price=1,
        )
        db.add_all([p1, p2]); db.commit(); db.refresh(p1); db.refresh(p2)

        # p1 활성 2, p1 만료 1, p2 HELD 1
        _make_member(db, branch, p1.id, "A", "M", "1990-01-01", "01000000001")
        _make_member(db, branch, p1.id, "B", "F", "1990-01-01", "01000000002")
        _make_member(db, branch, p1.id, "C", "M", "1990-01-01", "01000000003",
                     status="EXPIRED")
        _make_member(db, branch, p2.id, "D", "F", "1990-01-01", "01000000004",
                     status="HELD")

        res = client.get("/admin/dashboard/summary", headers=auth_super)
        body = res.json()
        by_pass = body["members"]["by_membership_pass"]
        assert by_pass[str(p1.id)] == 2  # 활성만, 만료 제외
        assert by_pass[str(p2.id)] == 1  # HELD 도 활성으로 카운트

    def test_recent_limit_5(self, client, db, auth_super, branch):
        """recent는 최근 5건만"""
        p = MembershipPass(
            branch_id=branch.id, name="1개월", cash_price=1, card_price=1,
        )
        db.add(p); db.commit(); db.refresh(p)

        for i in range(7):
            _make_member(
                db, branch, p.id, f"회원{i}", "M", "1990-01-01",
                f"010000{i:05d}",
            )

        res = client.get("/admin/dashboard/summary", headers=auth_super)
        body = res.json()
        assert len(body["members"]["recent"]) == 5

    def test_reservation_today_visit(self, client, db, auth_super, branch):
        """visit_date == today 카운트"""
        today = date.today()
        r1 = Reservation(branch_id=branch.id, name="오늘",
                         phone="01000000001", visit_date=today)
        r2 = Reservation(branch_id=branch.id, name="내일",
                         phone="01000000002", visit_date=today + timedelta(days=1))
        db.add_all([r1, r2]); db.commit()

        res = client.get("/admin/dashboard/summary", headers=auth_super)
        body = res.json()
        assert body["reservations"]["today_visit"] == 1
        assert body["reservations"]["total"] == 2

    def test_fc_scoped_to_own_branch(
        self, client, db, auth_fc, branch, branch_other,
    ):
        """FC는 자기 지점 데이터만 집계"""
        p_a = MembershipPass(
            branch_id=branch.id, name="A", cash_price=1, card_price=1,
        )
        p_b = MembershipPass(
            branch_id=branch_other.id, name="B", cash_price=1, card_price=1,
        )
        db.add_all([p_a, p_b]); db.commit(); db.refresh(p_a); db.refresh(p_b)
        _make_member(db, branch, p_a.id, "화순", "M", "1990-01-01", "01000000001")
        _make_member(db, branch_other, p_b.id, "첨단", "F", "1990-01-01", "01000000002")

        res = client.get("/admin/dashboard/summary", headers=auth_fc)
        body = res.json()
        # FC는 화순(branch) 1명만 집계
        assert body["members"]["total"] == 1

    def test_super_admin_branch_filter(
        self, client, db, auth_super, branch, branch_other,
    ):
        """SUPER_ADMIN은 branch_id 옵션으로 특정 지점만 볼 수 있음"""
        p_a = MembershipPass(
            branch_id=branch.id, name="A", cash_price=1, card_price=1,
        )
        p_b = MembershipPass(
            branch_id=branch_other.id, name="B", cash_price=1, card_price=1,
        )
        db.add_all([p_a, p_b]); db.commit(); db.refresh(p_a); db.refresh(p_b)
        _make_member(db, branch, p_a.id, "화순", "M", "1990-01-01", "01000000001")
        _make_member(db, branch_other, p_b.id, "첨단", "F", "1990-01-01", "01000000002")

        # branch_id 없음 → 전 지점
        res_all = client.get("/admin/dashboard/summary", headers=auth_super)
        assert res_all.json()["members"]["total"] == 2

        # branch_id 지정 → 그 지점만
        res_one = client.get(
            f"/admin/dashboard/summary?branch_id={branch.id}",
            headers=auth_super,
        )
        assert res_one.json()["members"]["total"] == 1
