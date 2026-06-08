"""상품(회원권/수강권/락커/운동복) 통합 테스트

회원권으로 전체 CRUD·권한·409를 검증하고, 4종 공통 Public 목록은 parametrize로 검증.
(4종은 구조가 동일하므로 회원권을 대표로 깊게 테스트)
"""
from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.models.passes.clothes import ClothesPass
from app.models.passes.locker import LockerPass
from app.models.passes.membership import MembershipPass
from app.models.passes.pt import PTPass
from app.models.registrations.member import Member


class TestMembershipPassCRUD:

    def test_super_admin_create(self, client, auth_super, branch):
        """SUPER_ADMIN 회원권 등록 → 201"""
        res = client.post(
            "/admin/membership-passes",
            headers=auth_super,
            json={
                "branch_id": str(branch.id), "name": "3개월",
                "cash_price": 270000, "card_price": 300000,
            },
        )
        assert res.status_code == 201, res.text
        assert res.json()["name"] == "3개월"

    def test_fc_create_own_branch(self, client, auth_fc, branch):
        """FC는 자기 지점 회원권 등록 가능"""
        res = client.post(
            "/admin/membership-passes",
            headers=auth_fc,
            json={
                "branch_id": str(branch.id), "name": "1개월",
                "cash_price": 100000, "card_price": 110000,
            },
        )
        assert res.status_code == 201, res.text

    def test_fc_create_other_branch_404(self, client, auth_fc, branch_other):
        """FC가 타 지점 회원권 등록 → 404"""
        res = client.post(
            "/admin/membership-passes",
            headers=auth_fc,
            json={
                "branch_id": str(branch_other.id), "name": "1개월",
                "cash_price": 100000, "card_price": 110000,
            },
        )
        assert res.status_code == 404

    def test_update(self, client, db, auth_super, branch):
        """회원권 부분 수정 (현금가)"""
        p = MembershipPass(
            branch_id=branch.id, name="1개월",
            cash_price=100000, card_price=110000,
        )
        db.add(p); db.commit(); db.refresh(p)
        res = client.patch(
            f"/admin/membership-passes/{p.id}",
            headers=auth_super,
            json={"cash_price": 95000},
        )
        assert res.status_code == 200
        assert res.json()["cash_price"] == 95000

    def test_update_duration_months_change(self, client, db, auth_super, branch):
        """duration_months 값 변경 (3 → 6) 이 정상 반영돼야 함"""
        p = MembershipPass(
            branch_id=branch.id, name="3개월",
            cash_price=270000, card_price=300000, duration_months=3,
        )
        db.add(p); db.commit(); db.refresh(p)
        res = client.patch(
            f"/admin/membership-passes/{p.id}",
            headers=auth_super,
            json={"duration_months": 6},
        )
        assert res.status_code == 200, res.text
        assert res.json()["duration_months"] == 6
        db.refresh(p)
        assert p.duration_months == 6

    def test_update_duration_months_clear_to_null(self, client, db, auth_super, branch):
        """duration_months 명시적 null 도 반영 — 비우기 의도 보존.

        이전 `if x is not None: ...` 패턴에선 null clear 가 무시되던 버그 회귀 방지.
        """
        p = MembershipPass(
            branch_id=branch.id, name="일권",
            cash_price=10000, card_price=12000, duration_months=1,
        )
        db.add(p); db.commit(); db.refresh(p)
        res = client.patch(
            f"/admin/membership-passes/{p.id}",
            headers=auth_super,
            json={"duration_months": None},
        )
        assert res.status_code == 200, res.text
        assert res.json()["duration_months"] is None
        db.refresh(p)
        assert p.duration_months is None

    def test_update_omit_field_keeps_value(self, client, db, auth_super, branch):
        """필드 누락(send 안 함) 시 기존 값 유지 — 진짜 부분 수정."""
        p = MembershipPass(
            branch_id=branch.id, name="3개월",
            cash_price=270000, card_price=300000, duration_months=3,
        )
        db.add(p); db.commit(); db.refresh(p)
        # cash_price 만 변경, duration_months 는 페이로드에 안 들어감
        res = client.patch(
            f"/admin/membership-passes/{p.id}",
            headers=auth_super,
            json={"cash_price": 280000},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["cash_price"] == 280000
        assert body["duration_months"] == 3  # 그대로 유지

    def test_create_with_duration_days(self, client, auth_super, branch):
        """일권 등록 — duration_days 만 채움"""
        res = client.post(
            "/admin/membership-passes",
            headers=auth_super,
            json={
                "branch_id": str(branch.id), "name": "7일권",
                "cash_price": 30000, "card_price": 33000,
                "duration_days": 7,
            },
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["duration_days"] == 7
        assert body["duration_months"] is None
        assert body["duration_hours"] is None

    def test_create_with_duration_hours(self, client, auth_super, branch):
        """시간권 등록 — duration_hours 만 채움"""
        res = client.post(
            "/admin/membership-passes",
            headers=auth_super,
            json={
                "branch_id": str(branch.id), "name": "3시간권",
                "cash_price": 10000, "card_price": 12000,
                "duration_hours": 3,
            },
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["duration_hours"] == 3
        assert body["duration_months"] is None
        assert body["duration_days"] is None

    def test_create_two_units_rejected(self, client, auth_super, branch):
        """months 와 days 둘 다 보내면 400 — 한 단위만 허용"""
        res = client.post(
            "/admin/membership-passes",
            headers=auth_super,
            json={
                "branch_id": str(branch.id), "name": "혼합",
                "cash_price": 100000, "card_price": 110000,
                "duration_months": 1, "duration_days": 7,
            },
        )
        assert res.status_code == 400, res.text
        assert "한 가지 단위" in res.json()["detail"]

    def test_update_switch_unit_clears_other(self, client, db, auth_super, branch):
        """개월 → 일 단위 전환 시 기존 개월값을 명시적 null 로 비워야 통과."""
        p = MembershipPass(
            branch_id=branch.id, name="기존 1개월",
            cash_price=100000, card_price=110000, duration_months=1,
        )
        db.add(p); db.commit(); db.refresh(p)
        res = client.patch(
            f"/admin/membership-passes/{p.id}",
            headers=auth_super,
            json={"duration_months": None, "duration_days": 7},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["duration_months"] is None
        assert body["duration_days"] == 7

    def test_update_conflict_rejected(self, client, db, auth_super, branch):
        """기존에 months 가 있는데 days 만 보내면 (months 그대로) → 두 단위 충돌 → 400."""
        p = MembershipPass(
            branch_id=branch.id, name="1개월",
            cash_price=100000, card_price=110000, duration_months=1,
        )
        db.add(p); db.commit(); db.refresh(p)
        res = client.patch(
            f"/admin/membership-passes/{p.id}",
            headers=auth_super,
            json={"duration_days": 7},  # months 는 그대로 1
        )
        assert res.status_code == 400, res.text
        assert "한 가지 단위" in res.json()["detail"]

    def test_delete(self, client, db, auth_super, branch):
        """미사용 회원권 삭제 → 204"""
        p = MembershipPass(
            branch_id=branch.id, name="1개월",
            cash_price=100000, card_price=110000,
        )
        db.add(p); db.commit(); db.refresh(p)
        res = client.delete(
            f"/admin/membership-passes/{p.id}", headers=auth_super,
        )
        assert res.status_code == 204
        assert db.query(MembershipPass).filter(
            MembershipPass.id == p.id
        ).first() is None

    def test_delete_in_use_409(self, client, db, auth_super, branch):
        """회원이 사용 중인 회원권 삭제 → 409"""
        p = MembershipPass(
            branch_id=branch.id, name="1개월",
            cash_price=100000, card_price=110000,
        )
        db.add(p); db.commit(); db.refresh(p)

        today = date.today()
        member = Member(
            branch_id=branch.id, membership_pass_id=p.id,
            name="사용중회원", gender="M", birth_date="1990-01-01",
            phone="01012341234", address="광주",
            referral="NAVER", payment_method="CARD", final_price=110000,
            start_date=today, end_date=today + timedelta(days=30),
            motivation="HEALTH_IMPROVEMENT", agreed_terms=True,
        )
        db.add(member); db.commit()

        res = client.delete(
            f"/admin/membership-passes/{p.id}", headers=auth_super,
        )
        assert res.status_code == 409

    def test_delete_nonexistent_404(self, client, auth_super):
        res = client.delete(
            f"/admin/membership-passes/{uuid4()}", headers=auth_super,
        )
        assert res.status_code == 404

    def test_no_auth_401(self, client):
        res = client.get("/admin/membership-passes")
        assert res.status_code == 401


class TestMembershipPassPermissions:

    def test_fc_list_only_own_branch(
        self, client, db, auth_fc, branch, branch_other,
    ):
        """FC는 자기 지점 회원권만 조회"""
        own = MembershipPass(
            branch_id=branch.id, name="자기지점",
            cash_price=100000, card_price=110000,
        )
        other = MembershipPass(
            branch_id=branch_other.id, name="타지점",
            cash_price=100000, card_price=110000,
        )
        db.add_all([own, other]); db.commit()

        res = client.get("/admin/membership-passes", headers=auth_fc)
        assert res.status_code == 200
        names = {p["name"] for p in res.json()}
        assert "자기지점" in names
        assert "타지점" not in names


class TestPublicPassList:
    """4종 상품 공통 Public 목록 조회 - branch_id 필수"""

    @pytest.mark.parametrize("path,model", [
        ("/membership-passes", MembershipPass),
        ("/pt-passes", PTPass),
        ("/locker-passes", LockerPass),
        ("/clothes-passes", ClothesPass),
    ])
    def test_public_list_returns_branch_passes(
        self, client, db, branch, path, model,
    ):
        """지점별 상품 목록 → 200 + 해당 지점 상품"""
        p = model(
            branch_id=branch.id, name="상품",
            cash_price=10000, card_price=11000,
        )
        db.add(p); db.commit()

        res = client.get(f"{path}?branch_id={branch.id}")
        assert res.status_code == 200, res.text
        body = res.json()
        assert len(body) == 1
        assert body[0]["name"] == "상품"

    @pytest.mark.parametrize("path", [
        "/membership-passes", "/pt-passes",
        "/locker-passes", "/clothes-passes",
    ])
    def test_public_list_requires_branch_id(self, client, path):
        """branch_id 없으면 422"""
        res = client.get(path)
        assert res.status_code == 422
