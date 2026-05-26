"""권한 분기 테스트 - FC는 자기 지점만, SUPER_ADMIN은 전 지점"""
import pytest

from app.models.passes.membership import MembershipPass
from app.models.registrations.member import Member


@pytest.fixture
def setup_two_branches_with_members(db, branch, branch_other):
    """화순점/첨단점 각각 회원 1명씩 + 회원권"""
    pass_a = MembershipPass(
        branch_id=branch.id, name="1개월",
        cash_price=100000, card_price=110000,
    )
    pass_b = MembershipPass(
        branch_id=branch_other.id, name="1개월",
        cash_price=100000, card_price=110000,
    )
    db.add_all([pass_a, pass_b]); db.commit()
    db.refresh(pass_a); db.refresh(pass_b)

    member_a = Member(
        branch_id=branch.id, membership_pass_id=pass_a.id,
        name="화순회원", gender="M", birth_date="1990-01-01",
        phone="01011111111", address="화순", referral="NAVER",
        payment_method="CARD", final_price=110000,
        start_date="2026-05-01", end_date="2026-06-01",
        motivation="HEALTH_IMPROVEMENT", agreed_terms=True,
    )
    member_b = Member(
        branch_id=branch_other.id, membership_pass_id=pass_b.id,
        name="첨단회원", gender="F", birth_date="1992-02-02",
        phone="01022222222", address="첨단", referral="FLYER",
        payment_method="CARD", final_price=110000,
        start_date="2026-05-01", end_date="2026-06-01",
        motivation="WEIGHT_LOSS", agreed_terms=True,
    )
    db.add_all([member_a, member_b]); db.commit()
    db.refresh(member_a); db.refresh(member_b)
    return {"branch_a": branch, "branch_b": branch_other,
            "member_a": member_a, "member_b": member_b}


class TestMemberListPermissions:

    def test_super_admin_sees_all_branches(
        self, client, auth_super, setup_two_branches_with_members,
    ):
        """SUPER_ADMIN은 branch 필터 없으면 전 지점 회원 다 봄"""
        res = client.get("/admin/members", headers=auth_super)
        assert res.status_code == 200
        members = res.json()["items"]
        names = {m["name"] for m in members}
        assert "화순회원" in names
        assert "첨단회원" in names

    def test_fc_sees_only_own_branch(
        self, client, auth_fc, setup_two_branches_with_members,
    ):
        """FC는 branch_id 안 줘도 자기 지점만 자동 필터"""
        res = client.get("/admin/members", headers=auth_fc)
        assert res.status_code == 200
        members = res.json()["items"]
        names = {m["name"] for m in members}
        assert "화순회원" in names
        assert "첨단회원" not in names

    def test_fc_branch_id_param_ignored(
        self, client, auth_fc, setup_two_branches_with_members,
    ):
        """FC가 다른 지점 branch_id 명시해도 자기 지점으로 강제 필터"""
        branch_b_id = setup_two_branches_with_members["branch_b"].id
        res = client.get(
            f"/admin/members?branch_id={branch_b_id}",
            headers=auth_fc,
        )
        assert res.status_code == 200
        names = {m["name"] for m in res.json()["items"]}
        assert "첨단회원" not in names
        assert "화순회원" in names


class TestMemberDetailPermissions:

    def test_fc_cannot_access_other_branch_member_404(
        self, client, auth_fc, setup_two_branches_with_members,
    ):
        """FC가 타 지점 회원 단건 조회 → 404 (정보 노출 최소화)"""
        member_b_id = setup_two_branches_with_members["member_b"].id
        res = client.get(f"/admin/members/{member_b_id}", headers=auth_fc)
        assert res.status_code == 404

    def test_super_admin_can_access_any_member(
        self, client, auth_super, setup_two_branches_with_members,
    ):
        """SUPER_ADMIN은 어느 지점이든 단건 조회 가능"""
        member_b_id = setup_two_branches_with_members["member_b"].id
        res = client.get(f"/admin/members/{member_b_id}", headers=auth_super)
        assert res.status_code == 200
        assert res.json()["name"] == "첨단회원"

    def test_no_auth_returns_401(
        self, client, setup_two_branches_with_members,
    ):
        """토큰 없이 admin 라우터 접근 → 401"""
        res = client.get("/admin/members")
        assert res.status_code == 401
