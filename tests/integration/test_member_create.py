"""POST /members 통합 테스트 - DB row 생성, 메시지 이력 저장, FK 검증"""
import pytest

from app.models.messaging.message import Message
from app.models.passes.clothes import ClothesPass
from app.models.passes.locker import LockerPass
from app.models.passes.membership import MembershipPass
from app.models.registrations.member import Member


@pytest.fixture
def membership_pass(db, branch):
    p = MembershipPass(
        branch_id=branch.id, name="1개월",
        cash_price=100000, card_price=110000,
    )
    db.add(p); db.commit(); db.refresh(p)
    return p


@pytest.fixture
def locker_pass(db, branch):
    p = LockerPass(
        branch_id=branch.id, name="락커 1개월",
        cash_price=30000, card_price=33000,
    )
    db.add(p); db.commit(); db.refresh(p)
    return p


@pytest.fixture
def clothes_pass(db, branch):
    p = ClothesPass(
        branch_id=branch.id, name="운동복 1개월",
        cash_price=20000, card_price=22000,
    )
    db.add(p); db.commit(); db.refresh(p)
    return p


def _member_payload(branch, membership_pass, **overrides):
    """필수 필드 다 채운 회원가입 payload"""
    payload = {
        "branch_id": str(branch.id),
        "membership_pass_id": str(membership_pass.id),
        "name": "김은후",
        "gender": "M",
        "birth_date": "1995-09-03",
        "phone": "01012345678",
        "address": "광주광역시 동구",
        "referral": "NAVER",
        "payment_method": "CARD",
        "final_price": 110000,
        "start_date": "2026-05-18",
        "end_date": "2026-06-18",
        "motivation": "WEIGHT_LOSS",
        "agreed_terms": True,
    }
    payload.update(overrides)
    return payload


class TestCreateMember:

    def test_create_member_minimal(
        self, client, db, branch, membership_pass,
    ):
        """필수 필드만으로 회원 등록 → 201 + DB row 1개"""
        res = client.post(
            "/members",
            json=_member_payload(branch, membership_pass),
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["name"] == "김은후"
        assert body["status"] == "REGISTERED"

        # DB 검증
        member = db.query(Member).filter(Member.phone == "01012345678").first()
        assert member is not None
        assert member.branch_id == branch.id
        assert member.locker_pass_id is None
        assert member.clothes_pass_id is None

    def test_create_member_with_locker_and_clothes(
        self, client, db, branch, membership_pass, locker_pass, clothes_pass,
    ):
        """락커·운동복 FK 포함 등록"""
        res = client.post(
            "/members",
            json=_member_payload(
                branch, membership_pass,
                locker_pass_id=str(locker_pass.id),
                clothes_pass_id=str(clothes_pass.id),
            ),
        )
        assert res.status_code == 201, res.text

        member = db.query(Member).filter(Member.phone == "01012345678").first()
        assert member.locker_pass_id == locker_pass.id
        assert member.clothes_pass_id == clothes_pass.id

    def test_create_member_logs_message_history(
        self, client, db, branch, membership_pass,
    ):
        """회원 등록 시 REGISTERED 알림톡 이력이 저장되어야 함 (Solapi는 mock됨)"""
        res = client.post(
            "/members",
            json=_member_payload(branch, membership_pass),
        )
        assert res.status_code == 201

        msg = db.query(Message).filter(
            Message.recipient == "01012345678"
        ).first()
        assert msg is not None
        assert msg.trigger_type == "REGISTERED"
        assert msg.status == "SUCCESS"  # mock이 (True, None) 반환

    def test_create_member_wrong_branch_pass_400(
        self, client, db, branch, branch_other, membership_pass,
    ):
        """타 지점 회원권 사용 시 400"""
        res = client.post(
            "/members",
            json=_member_payload(
                branch_other, membership_pass,  # 다른 지점인데 화순점 회원권
            ),
        )
        assert res.status_code == 400
        assert "지점" in res.json()["detail"]

    def test_create_member_invalid_phone_422(
        self, client, branch, membership_pass,
    ):
        """전화번호 형식 오류 시 422 (Pydantic validation)"""
        res = client.post(
            "/members",
            json=_member_payload(branch, membership_pass, phone="abc"),
        )
        assert res.status_code == 422
