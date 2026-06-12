"""다짐 얼굴 등록 통합 테스트 - 첨단점 회원가입·PT 신청 시 동기 처리"""
import json

import pytest

from app.models.passes.membership import MembershipPass
from app.models.passes.pt import PTPass
from app.models.registrations.member import Member
from app.models.registrations.pt_application import PTApplication
from app.services import dajim as dajim_service


def _tiny_jpeg() -> bytes:
    """Pillow로 1x1 흰색 JPEG 생성 (테스트 fixture용)"""
    from io import BytesIO
    from PIL import Image
    img = Image.new("RGB", (10, 10), color="white")
    out = BytesIO()
    img.save(out, format="JPEG")
    return out.getvalue()


_TINY_JPEG = _tiny_jpeg()


def _member_payload(branch, membership_pass, **overrides):
    p = {
        "branch_id": str(branch.id),
        "membership_pass_id": str(membership_pass.id),
        "name": "김첨단", "gender": "M", "birth_date": "1995-09-03",
        "phone": "01012345678", "address": "광주광역시 광산구",
        "referral": "NAVER", "payment_method": "CARD",
        "final_price": 100000,
        "start_date": "2026-06-12", "end_date": "2026-07-12",
        "motivation": "WEIGHT_LOSS", "agreed_terms": True,
    }
    p.update(overrides)
    return p


@pytest.fixture
def dajim_branch(db):
    """첨단점 - dajim_enabled + face_enabled"""
    from app.models.branch import Branch
    b = Branch(
        name="첨단점", phone="050-1111-2222",
        dajim_enabled=True,
        dajim_gym_id="test-gym-id",
        dajim_face_enabled=True,
    )
    db.add(b); db.commit(); db.refresh(b)
    return b


class TestCreateMemberFace:

    def test_dajim_branch_without_face_400(
        self, client, db, dajim_branch,
    ):
        """첨단점에서 face_image 없으면 400"""
        mp = MembershipPass(
            branch_id=dajim_branch.id, name="1개월",
            cash_price=1, card_price=1,
        )
        db.add(mp); db.commit(); db.refresh(mp)

        res = client.post(
            "/members",
            files={"payload": (None, json.dumps(
                _member_payload(dajim_branch, mp),
            ))},
        )
        assert res.status_code == 400
        assert "얼굴 사진" in res.json()["detail"]

    def test_dajim_branch_with_face_success(
        self, client, db, dajim_branch,
    ):
        """첨단점 + face_image → 다짐 mock 성공 → HiFIS 가입 OK, dajim_id 박힘"""
        mp = MembershipPass(
            branch_id=dajim_branch.id, name="1개월",
            cash_price=1, card_price=1,
        )
        db.add(mp); db.commit(); db.refresh(mp)

        res = client.post(
            "/members",
            data={"payload": json.dumps(_member_payload(
                dajim_branch, mp, phone="01088990001",
            ))},
            files={"face_image": ("face.jpg", _TINY_JPEG, "image/jpeg")},
        )
        assert res.status_code == 201, res.text

        member = db.query(Member).filter(
            Member.phone == "01088990001",
        ).first()
        assert member is not None
        assert member.dajim_id == "dajim-test-id"
        assert member.dajim_face_registered is True

    def test_dajim_face_failure_blocks_signup(
        self, client, db, dajim_branch, monkeypatch,
    ):
        """다짐 RegisterFace 실패 → 400 + HiFIS Member row 없음"""
        def fail(**kw):
            raise dajim_service.DajimSyncError(
                "얼굴 인증에 실패했습니다. 정면에서 얼굴이 잘 보이게 다시 찍어주세요.",
            )
        monkeypatch.setattr(
            "app.services.dajim.register_member_with_face_sync", fail,
        )

        mp = MembershipPass(
            branch_id=dajim_branch.id, name="1개월",
            cash_price=1, card_price=1,
        )
        db.add(mp); db.commit(); db.refresh(mp)

        res = client.post(
            "/members",
            data={"payload": json.dumps(_member_payload(
                dajim_branch, mp, phone="01088990002",
            ))},
            files={"face_image": ("face.jpg", _TINY_JPEG, "image/jpeg")},
        )
        assert res.status_code == 400
        assert "얼굴 인증" in res.json()["detail"]

        # HiFIS row 없음
        assert db.query(Member).filter(
            Member.phone == "01088990002",
        ).first() is None

    def test_non_dajim_branch_no_face_required(
        self, client, db, branch,
    ):
        """일반 지점(화순) - face_image 없어도 가입 OK (다짐 미사용)"""
        mp = MembershipPass(
            branch_id=branch.id, name="1개월",
            cash_price=1, card_price=1,
        )
        db.add(mp); db.commit(); db.refresh(mp)

        res = client.post(
            "/members",
            json=_member_payload(branch, mp, phone="01088990003"),
        )
        assert res.status_code == 201
        member = db.query(Member).filter(
            Member.phone == "01088990003",
        ).first()
        assert member.dajim_id is None
        assert member.dajim_face_registered is None


class TestCreatePTFace:

    def test_pt_dajim_branch_without_face_400(
        self, client, db, dajim_branch,
    ):
        """첨단점 PT 신청 시 face_image 없으면 400"""
        pp = PTPass(
            branch_id=dajim_branch.id, name="PT 10회",
            cash_price=1, card_price=1,
        )
        db.add(pp); db.commit(); db.refresh(pp)

        payload = {
            "branch_id": str(dajim_branch.id),
            "pt_pass_id": str(pp.id),
            "name": "PT첨단", "gender": "M", "birth_date": "1995-09-03",
            "phone": "01077665544", "address": "광주",
            "referral": "NAVER", "payment_method": "CARD",
            "final_price": 500000,
            "start_date": "2026-06-12", "end_date": "2026-07-12",
            "agreed_notice": True,
        }
        res = client.post(
            "/pt-applications",
            files={"payload": (None, json.dumps(payload))},
        )
        assert res.status_code == 400
        assert "얼굴 사진" in res.json()["detail"]

    def test_pt_with_face_success(self, client, db, dajim_branch):
        """첨단점 PT 신청 + face → 성공, dajim_id 박힘"""
        pp = PTPass(
            branch_id=dajim_branch.id, name="PT 10회",
            cash_price=1, card_price=1,
        )
        db.add(pp); db.commit(); db.refresh(pp)

        payload = {
            "branch_id": str(dajim_branch.id),
            "pt_pass_id": str(pp.id),
            "name": "PT첨단2", "gender": "M", "birth_date": "1995-09-03",
            "phone": "01077665555", "address": "광주",
            "referral": "NAVER", "payment_method": "CARD",
            "final_price": 500000,
            "start_date": "2026-06-12", "end_date": "2026-07-12",
            "agreed_notice": True,
        }
        res = client.post(
            "/pt-applications",
            data={"payload": json.dumps(payload)},
            files={"face_image": ("face.jpg", _TINY_JPEG, "image/jpeg")},
        )
        assert res.status_code == 201, res.text
        app = db.query(PTApplication).filter(
            PTApplication.phone == "01077665555",
        ).first()
        assert app.dajim_id == "dajim-test-id"
        assert app.dajim_face_registered is True
