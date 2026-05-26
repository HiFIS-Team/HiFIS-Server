"""PT 신청 통합 테스트 - POST /pt-applications, GET/PATCH/DELETE /admin/pt-applications"""
from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.models.messaging.message import Message
from app.models.passes.pt import PTPass
from app.models.registrations.pt_application import PTApplication


@pytest.fixture
def pt_pass(db, branch):
    """화순점 수강권"""
    p = PTPass(
        branch_id=branch.id, name="PT 10회",
        cash_price=500000, card_price=550000,
    )
    db.add(p); db.commit(); db.refresh(p)
    return p


@pytest.fixture
def pt_pass_other(db, branch_other):
    """첨단점 수강권 (타 지점 검증용)"""
    p = PTPass(
        branch_id=branch_other.id, name="PT 10회",
        cash_price=500000, card_price=550000,
    )
    db.add(p); db.commit(); db.refresh(p)
    return p


@pytest.fixture
def pt_application(db, branch, pt_pass):
    """화순점 기존 PT 신청 1건"""
    today = date.today()
    app_ = PTApplication(
        branch_id=branch.id, pt_pass_id=pt_pass.id,
        name="기존신청", gender="M", birth_date="1990-01-01",
        phone="01099998888", address="광주",
        referral="NAVER", payment_method="CARD", final_price=550000,
        start_date=today, end_date=today + timedelta(days=90),
        agreed_notice=True,
    )
    db.add(app_); db.commit(); db.refresh(app_)
    return app_


@pytest.fixture
def pt_application_other(db, branch_other, pt_pass_other):
    """첨단점 PT 신청 1건 (타 지점 권한 검증용)"""
    today = date.today()
    app_ = PTApplication(
        branch_id=branch_other.id, pt_pass_id=pt_pass_other.id,
        name="타지점신청", gender="F", birth_date="1992-02-02",
        phone="01077776666", address="첨단",
        referral="FLYER", payment_method="CARD", final_price=550000,
        start_date=today, end_date=today + timedelta(days=90),
        agreed_notice=True,
    )
    db.add(app_); db.commit(); db.refresh(app_)
    return app_


def _pt_payload(branch, pt_pass, **overrides):
    """필수 필드 다 채운 PT 신청 payload"""
    today = date.today()
    payload = {
        "branch_id": str(branch.id),
        "pt_pass_id": str(pt_pass.id),
        "name": "김피티",
        "gender": "M",
        "birth_date": "1995-09-03",
        "phone": "01012345678",
        "address": "광주광역시 동구",
        "referral": "NAVER",
        "payment_method": "CARD",
        "final_price": 550000,
        "start_date": str(today),
        "end_date": str(today + timedelta(days=90)),
        "agreed_notice": True,
    }
    payload.update(overrides)
    return payload


class TestCreatePTApplication:

    def test_create_pt_application(self, client, db, branch, pt_pass):
        """PT 신청 → 201 + DB row 1개"""
        res = client.post("/pt-applications", json=_pt_payload(branch, pt_pass))
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["name"] == "김피티"
        assert body["status"] == "REGISTERED"

        row = db.query(PTApplication).filter(
            PTApplication.phone == "01012345678"
        ).first()
        assert row is not None
        assert row.branch_id == branch.id

    def test_create_logs_message(self, client, db, branch, pt_pass):
        """PT 신청 시 REGISTERED 알림톡 이력 저장"""
        res = client.post("/pt-applications", json=_pt_payload(branch, pt_pass))
        assert res.status_code == 201

        msg = db.query(Message).filter(
            Message.recipient == "01012345678"
        ).first()
        assert msg is not None
        assert msg.trigger_type == "REGISTERED"

    def test_create_wrong_branch_pass_400(self, client, branch, pt_pass_other):
        """타 지점 수강권 사용 → 400"""
        res = client.post(
            "/pt-applications", json=_pt_payload(branch, pt_pass_other),
        )
        assert res.status_code == 400
        assert "지점" in res.json()["detail"]

    def test_create_nonexistent_pass_404(self, client, branch, pt_pass):
        """존재하지 않는 수강권 → 404"""
        res = client.post(
            "/pt-applications",
            json=_pt_payload(branch, pt_pass, pt_pass_id=str(uuid4())),
        )
        assert res.status_code == 404

    def test_create_agreed_notice_false_422(self, client, branch, pt_pass):
        """유의사항 미동의 → 422 (Pydantic validation)"""
        res = client.post(
            "/pt-applications",
            json=_pt_payload(branch, pt_pass, agreed_notice=False),
        )
        assert res.status_code == 422


class TestPTApplicationAdmin:

    def test_list_fc_only_own_branch(
        self, client, auth_fc, pt_application, pt_application_other,
    ):
        """FC는 자기 지점 PT 신청만 조회"""
        res = client.get("/admin/pt-applications", headers=auth_fc)
        assert res.status_code == 200
        names = {a["name"] for a in res.json()}
        assert "기존신청" in names
        assert "타지점신청" not in names

    def test_get_detail(self, client, auth_super, pt_application):
        res = client.get(
            f"/admin/pt-applications/{pt_application.id}", headers=auth_super,
        )
        assert res.status_code == 200
        assert res.json()["name"] == "기존신청"

    def test_fc_cannot_get_other_branch_404(
        self, client, auth_fc, pt_application_other,
    ):
        """FC가 타 지점 PT 신청 단건 조회 → 404"""
        res = client.get(
            f"/admin/pt-applications/{pt_application_other.id}", headers=auth_fc,
        )
        assert res.status_code == 404

    def test_update_pt_application(self, client, db, auth_super, pt_application):
        """PT 신청 부분 수정 (이름)"""
        res = client.patch(
            f"/admin/pt-applications/{pt_application.id}",
            headers=auth_super,
            json={"name": "이름변경"},
        )
        assert res.status_code == 200
        assert res.json()["name"] == "이름변경"
        db.refresh(pt_application)
        assert pt_application.name == "이름변경"

    def test_delete_pt_application(self, client, db, auth_super, pt_application):
        """PT 신청 삭제 → 204 + DB row 제거"""
        res = client.delete(
            f"/admin/pt-applications/{pt_application.id}", headers=auth_super,
        )
        assert res.status_code == 204
        assert db.query(PTApplication).filter(
            PTApplication.id == pt_application.id
        ).first() is None

    def test_no_auth_401(self, client):
        res = client.get("/admin/pt-applications")
        assert res.status_code == 401


# === Phase A 추가 필드: motivation / locker_pass_id / clothes_pass_id ===

@pytest.fixture
def locker_pass_pt(db, branch):
    """화순점 락커 상품 (PT용 0원)"""
    from app.models.passes.locker import LockerPass
    p = LockerPass(
        branch_id=branch.id, name="PT 락커 1개월",
        cash_price=0, card_price=0,
    )
    db.add(p); db.commit(); db.refresh(p)
    return p


@pytest.fixture
def clothes_pass_pt(db, branch):
    """화순점 운동복 상품 (PT용 0원)"""
    from app.models.passes.clothes import ClothesPass
    p = ClothesPass(
        branch_id=branch.id, name="PT 운동복 1개월",
        cash_price=0, card_price=0,
    )
    db.add(p); db.commit(); db.refresh(p)
    return p


@pytest.fixture
def locker_pass_other_branch(db, branch_other):
    """첨단점 락커 상품 (지점 검증용)"""
    from app.models.passes.locker import LockerPass
    p = LockerPass(
        branch_id=branch_other.id, name="락커",
        cash_price=0, card_price=0,
    )
    db.add(p); db.commit(); db.refresh(p)
    return p


class TestPTApplicationOptionalFields:

    def test_create_with_motivation(self, client, db, branch, pt_pass):
        """PT 신청 시 motivation 함께 저장"""
        res = client.post(
            "/pt-applications",
            json=_pt_payload(branch, pt_pass, motivation="WEIGHT_LOSS"),
        )
        assert res.status_code == 201, res.text
        row = db.query(PTApplication).filter(
            PTApplication.phone == "01012345678"
        ).first()
        assert row.motivation == "WEIGHT_LOSS"

    def test_create_with_locker_and_clothes(
        self, client, db, branch, pt_pass, locker_pass_pt, clothes_pass_pt,
    ):
        """락커·운동복 FK 함께 저장"""
        res = client.post(
            "/pt-applications",
            json=_pt_payload(
                branch, pt_pass,
                locker_pass_id=str(locker_pass_pt.id),
                clothes_pass_id=str(clothes_pass_pt.id),
            ),
        )
        assert res.status_code == 201, res.text
        row = db.query(PTApplication).filter(
            PTApplication.phone == "01012345678"
        ).first()
        assert row.locker_pass_id == locker_pass_pt.id
        assert row.clothes_pass_id == clothes_pass_pt.id

    def test_create_with_wrong_branch_locker_400(
        self, client, branch, pt_pass, locker_pass_other_branch,
    ):
        """타 지점 락커 사용 → 400"""
        res = client.post(
            "/pt-applications",
            json=_pt_payload(
                branch, pt_pass,
                locker_pass_id=str(locker_pass_other_branch.id),
            ),
        )
        assert res.status_code == 400
        assert "지점" in res.json()["detail"]

    def test_create_without_optionals_still_works(
        self, client, db, branch, pt_pass,
    ):
        """기존 회귀 — motivation/locker/clothes 없이도 정상 생성, NULL 저장"""
        res = client.post(
            "/pt-applications", json=_pt_payload(branch, pt_pass),
        )
        assert res.status_code == 201
        row = db.query(PTApplication).filter(
            PTApplication.phone == "01012345678"
        ).first()
        assert row.motivation is None
        assert row.locker_pass_id is None
        assert row.clothes_pass_id is None
