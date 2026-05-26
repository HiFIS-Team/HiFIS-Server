"""통계 통합 테스트 - GET /admin/stats/referral · /motivation

통계는 이번 달(created_at 기준) Member·PTApplication을 집계하므로
테스트에서 만든 회원은 모두 이번 달에 잡힌다.
"""
from datetime import date, timedelta

from app.models.passes.membership import MembershipPass
from app.models.passes.pt import PTPass
from app.models.registrations.member import Member
from app.models.registrations.pt_application import PTApplication


def _make_member(db, branch, pass_id, referral, motivation, phone):
    """집계 검증용 회원 1명 생성"""
    today = date.today()
    m = Member(
        branch_id=branch.id, membership_pass_id=pass_id,
        name="통계회원", gender="M", birth_date="1990-01-01",
        phone=phone, address="광주",
        referral=referral, payment_method="CARD", final_price=1,
        start_date=today, end_date=today + timedelta(days=30),
        motivation=motivation, agreed_terms=True,
    )
    db.add(m); db.commit()
    return m


def _count_for(items, code):
    """통계 응답 items에서 code의 count 추출"""
    for item in items:
        if item["code"] == code:
            return item["count"]
    return None


class TestReferralStats:

    def test_referral_counts(self, client, db, auth_super, branch):
        """유입경로별 카운트 집계"""
        p = MembershipPass(
            branch_id=branch.id, name="1개월", cash_price=1, card_price=1,
        )
        db.add(p); db.commit(); db.refresh(p)
        _make_member(db, branch, p.id, "NAVER", "WEIGHT_LOSS", "01000000001")
        _make_member(db, branch, p.id, "NAVER", "WEIGHT_LOSS", "01000000002")
        _make_member(db, branch, p.id, "FLYER", "MUSCLE_GAIN", "01000000003")

        res = client.get("/admin/stats/referral", headers=auth_super)
        assert res.status_code == 200
        body = res.json()
        assert _count_for(body["items"], "NAVER") == 2
        assert _count_for(body["items"], "FLYER") == 1
        assert body["total"] == 3

    def test_referral_includes_pt_applications(
        self, client, db, auth_super, branch,
    ):
        """유입경로 통계는 Member + PTApplication 합산"""
        mp = MembershipPass(
            branch_id=branch.id, name="1개월", cash_price=1, card_price=1,
        )
        pp = PTPass(
            branch_id=branch.id, name="PT 10회", cash_price=1, card_price=1,
        )
        db.add_all([mp, pp]); db.commit(); db.refresh(mp); db.refresh(pp)

        _make_member(db, branch, mp.id, "NAVER", "WEIGHT_LOSS", "01000000001")
        today = date.today()
        pt = PTApplication(
            branch_id=branch.id, pt_pass_id=pp.id,
            name="PT신청", gender="M", birth_date="1990-01-01",
            phone="01000000009", address="광주",
            referral="NAVER", payment_method="CARD", final_price=1,
            start_date=today, end_date=today + timedelta(days=30),
            agreed_notice=True,
        )
        db.add(pt); db.commit()

        res = client.get("/admin/stats/referral", headers=auth_super)
        assert res.status_code == 200
        # Member 1 + PT 1 = NAVER 2
        assert _count_for(res.json()["items"], "NAVER") == 2


class TestMotivationStats:

    def test_motivation_counts(self, client, db, auth_super, branch):
        """방문목적별 카운트 집계 (Member 기준)"""
        p = MembershipPass(
            branch_id=branch.id, name="1개월", cash_price=1, card_price=1,
        )
        db.add(p); db.commit(); db.refresh(p)
        _make_member(db, branch, p.id, "NAVER", "WEIGHT_LOSS", "01000000001")
        _make_member(db, branch, p.id, "NAVER", "WEIGHT_LOSS", "01000000002")
        _make_member(db, branch, p.id, "NAVER", "POSTURE_CORRECTION", "01000000003")

        res = client.get("/admin/stats/motivation", headers=auth_super)
        assert res.status_code == 200
        body = res.json()
        assert _count_for(body["items"], "WEIGHT_LOSS") == 2
        assert _count_for(body["items"], "POSTURE_CORRECTION") == 1
        assert body["total"] == 3


class TestStatsPermissions:

    def test_fc_stats_scoped_to_own_branch(
        self, client, db, auth_fc, branch, branch_other,
    ):
        """FC 통계는 자기 지점만 집계 (타 지점 제외)"""
        p_a = MembershipPass(
            branch_id=branch.id, name="1개월", cash_price=1, card_price=1,
        )
        p_b = MembershipPass(
            branch_id=branch_other.id, name="1개월", cash_price=1, card_price=1,
        )
        db.add_all([p_a, p_b]); db.commit(); db.refresh(p_a); db.refresh(p_b)
        _make_member(db, branch, p_a.id, "NAVER", "WEIGHT_LOSS", "01000000001")
        _make_member(db, branch_other, p_b.id, "NAVER", "WEIGHT_LOSS", "01000000002")

        res = client.get("/admin/stats/referral", headers=auth_fc)
        assert res.status_code == 200
        body = res.json()
        # FC는 자기 지점(화순) 1건만 집계
        assert _count_for(body["items"], "NAVER") == 1
        assert body["total"] == 1

    def test_no_auth_401(self, client):
        res = client.get("/admin/stats/referral")
        assert res.status_code == 401


class TestMotivationIncludesPT:
    """방문목적 통계는 Member + PTApplication 합산 (Phase A 변경)"""

    def test_pt_motivation_counted_with_member(
        self, client, db, auth_super, branch,
    ):
        """Member 1명(WEIGHT_LOSS) + PT 1건(WEIGHT_LOSS) → count 2"""
        mp = MembershipPass(
            branch_id=branch.id, name="1개월", cash_price=1, card_price=1,
        )
        pp = PTPass(
            branch_id=branch.id, name="PT", cash_price=1, card_price=1,
        )
        db.add_all([mp, pp]); db.commit(); db.refresh(mp); db.refresh(pp)
        _make_member(db, branch, mp.id, "NAVER", "WEIGHT_LOSS", "01000000001")

        today = date.today()
        pt = PTApplication(
            branch_id=branch.id, pt_pass_id=pp.id,
            name="PT", gender="M", birth_date="1990-01-01",
            phone="01000000002", address="광주",
            referral="NAVER", payment_method="CARD", final_price=1,
            start_date=today, end_date=today + timedelta(days=30),
            motivation="WEIGHT_LOSS",
            agreed_notice=True,
        )
        db.add(pt); db.commit()

        res = client.get("/admin/stats/motivation", headers=auth_super)
        assert res.status_code == 200
        assert _count_for(res.json()["items"], "WEIGHT_LOSS") == 2

    def test_pt_with_null_motivation_skipped(
        self, client, db, auth_super, branch,
    ):
        """PT의 motivation이 NULL이면 집계 제외 (Member도 없으면 total=0)"""
        pp = PTPass(
            branch_id=branch.id, name="PT", cash_price=1, card_price=1,
        )
        db.add(pp); db.commit(); db.refresh(pp)
        today = date.today()
        pt = PTApplication(
            branch_id=branch.id, pt_pass_id=pp.id,
            name="PT", gender="M", birth_date="1990-01-01",
            phone="01000000003", address="광주",
            referral="NAVER", payment_method="CARD", final_price=1,
            start_date=today, end_date=today + timedelta(days=30),
            motivation=None,
            agreed_notice=True,
        )
        db.add(pt); db.commit()

        res = client.get("/admin/stats/motivation", headers=auth_super)
        assert res.status_code == 200
        assert res.json()["total"] == 0
