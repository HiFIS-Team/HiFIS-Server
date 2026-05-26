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
