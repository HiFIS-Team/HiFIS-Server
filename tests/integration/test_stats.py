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


class TestMonthParam:
    """month 쿼리 파라미터 - YYYY-MM 형식, 미지정 시 이번 달"""

    def test_current_month_explicit(self, client, db, auth_super, branch):
        """month=이번달YYYY-MM 명시 → 미지정 응답과 동일"""
        p = MembershipPass(
            branch_id=branch.id, name="1개월", cash_price=1, card_price=1,
        )
        db.add(p); db.commit(); db.refresh(p)
        _make_member(db, branch, p.id, "NAVER", "WEIGHT_LOSS", "01000000001")

        today = date.today()
        ym = f"{today.year}-{today.month:02d}"
        res_with = client.get(
            f"/admin/stats/referral?month={ym}", headers=auth_super,
        )
        res_no = client.get("/admin/stats/referral", headers=auth_super)
        assert res_with.status_code == 200
        assert res_no.status_code == 200
        assert res_with.json()["total"] == res_no.json()["total"] == 1

    def test_past_month_zero(self, client, db, auth_super, branch):
        """과거 달 → 0 (이번 달에 만든 회원은 안 잡힘)"""
        p = MembershipPass(
            branch_id=branch.id, name="1개월", cash_price=1, card_price=1,
        )
        db.add(p); db.commit(); db.refresh(p)
        _make_member(db, branch, p.id, "NAVER", "WEIGHT_LOSS", "01000000001")

        res = client.get(
            "/admin/stats/referral?month=2020-01", headers=auth_super,
        )
        assert res.status_code == 200
        assert res.json()["total"] == 0

    def test_invalid_format_422(self, client, auth_super):
        """잘못된 형식 → 422 (Pydantic Query 패턴 검증)"""
        for bad in ["2026-5", "2026/05", "26-05", "2026-13", "abc"]:
            res = client.get(
                f"/admin/stats/referral?month={bad}", headers=auth_super,
            )
            assert res.status_code == 422, f"{bad} should be 422"

    def test_motivation_month_param(self, client, db, auth_super, branch):
        """motivation 통계도 month 받음"""
        p = MembershipPass(
            branch_id=branch.id, name="1개월", cash_price=1, card_price=1,
        )
        db.add(p); db.commit(); db.refresh(p)
        _make_member(db, branch, p.id, "NAVER", "WEIGHT_LOSS", "01000000001")

        res = client.get(
            "/admin/stats/motivation?month=2020-01", headers=auth_super,
        )
        assert res.status_code == 200
        assert res.json()["total"] == 0


class TestPassSalesStats:
    """GET /admin/stats/passes - 4종 묶음 (회원권/PT/락커/운동복)"""

    def test_response_has_four_categories(self, client, auth_super, branch):
        """응답에 4종 카테고리 다 포함, 데이터 없으면 빈 배열·total 0"""
        res = client.get("/admin/stats/passes", headers=auth_super)
        assert res.status_code == 200
        body = res.json()
        for key in ("membership", "pt", "locker", "clothes"):
            assert key in body
            assert body[key] == {"items": [], "total": 0}

    def test_membership_counts(self, client, db, auth_super, branch):
        """회원권 — 가입자 카운트 + zero-pass도 응답 포함"""
        from app.models.passes.locker import LockerPass
        p1 = MembershipPass(
            branch_id=branch.id, name="1개월", cash_price=1, card_price=1,
        )
        p2 = MembershipPass(
            branch_id=branch.id, name="3개월", cash_price=1, card_price=1,
        )
        db.add_all([p1, p2]); db.commit(); db.refresh(p1); db.refresh(p2)
        _make_member(db, branch, p1.id, "NAVER", "WEIGHT_LOSS", "01000000001")
        _make_member(db, branch, p1.id, "NAVER", "WEIGHT_LOSS", "01000000002")

        res = client.get("/admin/stats/passes", headers=auth_super)
        body = res.json()["membership"]
        # p1 = 2, p2 = 0 (zero-pass도 포함)
        items_by_id = {item["code"]: item for item in body["items"]}
        assert items_by_id[str(p1.id)]["count"] == 2
        assert items_by_id[str(p1.id)]["label"] == "1개월"
        assert items_by_id[str(p2.id)]["count"] == 0
        assert body["total"] == 2

    def test_locker_sums_member_and_pt(self, client, db, auth_super, branch):
        """락커 — Member.locker_pass_id + PTApplication.locker_pass_id 합산"""
        from app.models.passes.locker import LockerPass
        mp = MembershipPass(
            branch_id=branch.id, name="1개월", cash_price=1, card_price=1,
        )
        pp = PTPass(
            branch_id=branch.id, name="PT 10회", cash_price=1, card_price=1,
        )
        lp = LockerPass(
            branch_id=branch.id, name="락커 1개월", cash_price=1, card_price=1,
        )
        db.add_all([mp, pp, lp]); db.commit()
        db.refresh(mp); db.refresh(pp); db.refresh(lp)

        # Member 1명 (락커 사용)
        today = date.today()
        m = Member(
            branch_id=branch.id, membership_pass_id=mp.id, locker_pass_id=lp.id,
            name="M", gender="M", birth_date="1990-01-01",
            phone="01099990001", address="광주",
            referral="NAVER", payment_method="CARD", final_price=1,
            start_date=today, end_date=today + timedelta(days=30),
            motivation="WEIGHT_LOSS", agreed_terms=True,
        )
        # PT 1건 (락커 사용)
        pt = PTApplication(
            branch_id=branch.id, pt_pass_id=pp.id, locker_pass_id=lp.id,
            name="P", gender="M", birth_date="1990-01-01",
            phone="01099990002", address="광주",
            referral="NAVER", payment_method="CARD", final_price=1,
            start_date=today, end_date=today + timedelta(days=30),
            motivation="WEIGHT_LOSS",
            agreed_notice=True,
        )
        db.add_all([m, pt]); db.commit()

        res = client.get("/admin/stats/passes", headers=auth_super)
        locker = res.json()["locker"]
        assert locker["items"][0]["code"] == str(lp.id)
        assert locker["items"][0]["count"] == 2  # Member + PT
        assert locker["total"] == 2

    def test_branch_isolation_fc(self, client, db, auth_fc, branch, branch_other):
        """FC는 본인 지점 상품만 응답 (타 지점 pass 안 보임)"""
        from app.models.passes.locker import LockerPass
        p_mine = MembershipPass(
            branch_id=branch.id, name="우리지점", cash_price=1, card_price=1,
        )
        p_other = MembershipPass(
            branch_id=branch_other.id, name="다른지점", cash_price=1, card_price=1,
        )
        db.add_all([p_mine, p_other]); db.commit()

        res = client.get("/admin/stats/passes", headers=auth_fc)
        codes = {item["code"] for item in res.json()["membership"]["items"]}
        assert str(p_mine.id) in codes
        assert str(p_other.id) not in codes

    def test_past_month_zero(self, client, db, auth_super, branch):
        """과거 달 → 0"""
        p = MembershipPass(
            branch_id=branch.id, name="1개월", cash_price=1, card_price=1,
        )
        db.add(p); db.commit(); db.refresh(p)
        _make_member(db, branch, p.id, "NAVER", "WEIGHT_LOSS", "01000000001")

        res = client.get(
            "/admin/stats/passes?month=2020-01", headers=auth_super,
        )
        assert res.status_code == 200
        assert res.json()["membership"]["total"] == 0


class TestCategoryStats:
    """GET /admin/stats/category - 신규/재등록 회원·PT 묶음"""

    def test_response_shape(self, client, auth_super, branch):
        """빈 응답 형식 - member·pt 둘 다 NEW/EXISTING 0건"""
        res = client.get("/admin/stats/category", headers=auth_super)
        assert res.status_code == 200
        body = res.json()
        for key in ("member", "pt"):
            assert {item["code"] for item in body[key]["items"]} == {
                "NEW", "EXISTING",
            }
            assert all(item["count"] == 0 for item in body[key]["items"])
            assert body[key]["total"] == 0

    def test_member_category_counts(self, client, db, auth_super, branch):
        """Member NEW 2 + EXISTING 1 (직접 DB 입력)"""
        p = MembershipPass(
            branch_id=branch.id, name="1개월", cash_price=1, card_price=1,
        )
        db.add(p); db.commit(); db.refresh(p)
        # NEW 2명 (_make_member 디폴트가 NEW)
        _make_member(db, branch, p.id, "NAVER", "WEIGHT_LOSS", "01000000001")
        _make_member(db, branch, p.id, "NAVER", "WEIGHT_LOSS", "01000000002")
        # EXISTING 1명 직접 INSERT
        today = date.today()
        m_existing = Member(
            branch_id=branch.id, membership_pass_id=p.id,
            name="재등록회원", gender="M", birth_date="1990-01-01",
            phone="01000000099", address="광주",
            referral="NAVER", payment_method="CARD", final_price=1,
            start_date=today, end_date=today + timedelta(days=30),
            motivation="WEIGHT_LOSS", agreed_terms=True,
            category="EXISTING",
        )
        db.add(m_existing); db.commit()

        res = client.get("/admin/stats/category", headers=auth_super)
        member = res.json()["member"]
        items = {it["code"]: it for it in member["items"]}
        assert items["NEW"]["count"] == 2
        assert items["NEW"]["label"] == "신규"
        assert items["EXISTING"]["count"] == 1
        assert items["EXISTING"]["label"] == "재등록"
        assert member["total"] == 3

    def test_pt_category_counts(self, client, db, auth_super, branch):
        """PTApplication NEW 1 + EXISTING 1"""
        pp = PTPass(
            branch_id=branch.id, name="PT", cash_price=1, card_price=1,
        )
        db.add(pp); db.commit(); db.refresh(pp)
        today = date.today()
        for phone, cat in [("01000000201", "NEW"), ("01000000202", "EXISTING")]:
            pt = PTApplication(
                branch_id=branch.id, pt_pass_id=pp.id,
                name="P", gender="M", birth_date="1990-01-01",
                phone=phone, address="광주",
                referral="NAVER", payment_method="CARD", final_price=1,
                start_date=today, end_date=today + timedelta(days=30),
                motivation="WEIGHT_LOSS",
                agreed_notice=True,
                category=cat,
            )
            db.add(pt)
        db.commit()

        res = client.get("/admin/stats/category", headers=auth_super)
        pt_stats = res.json()["pt"]
        items = {it["code"]: it["count"] for it in pt_stats["items"]}
        assert items == {"NEW": 1, "EXISTING": 1}
        assert pt_stats["total"] == 2

    def test_fc_scoped_to_own_branch(
        self, client, db, auth_fc, branch, branch_other,
    ):
        """FC 호출 시 타 지점 카운트 안 보임"""
        p_mine = MembershipPass(
            branch_id=branch.id, name="우리", cash_price=1, card_price=1,
        )
        p_other = MembershipPass(
            branch_id=branch_other.id, name="다른", cash_price=1, card_price=1,
        )
        db.add_all([p_mine, p_other]); db.commit()
        db.refresh(p_mine); db.refresh(p_other)
        _make_member(db, branch, p_mine.id, "NAVER", "WEIGHT_LOSS", "01000000301")
        _make_member(
            db, branch_other, p_other.id, "NAVER", "WEIGHT_LOSS", "01000000302",
        )

        res = client.get("/admin/stats/category", headers=auth_fc)
        # FC는 본인 지점(branch)만 → 1건만 보임
        assert res.json()["member"]["total"] == 1

    def test_month_param(self, client, db, auth_super, branch):
        """과거 달 → 0"""
        p = MembershipPass(
            branch_id=branch.id, name="1개월", cash_price=1, card_price=1,
        )
        db.add(p); db.commit(); db.refresh(p)
        _make_member(db, branch, p.id, "NAVER", "WEIGHT_LOSS", "01000000001")

        res = client.get(
            "/admin/stats/category?month=2020-01", headers=auth_super,
        )
        assert res.status_code == 200
        assert res.json()["member"]["total"] == 0
