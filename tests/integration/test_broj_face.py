"""브로제이 얼굴 등록 통합 테스트 - 화순점 회원가입·PT 신청 동기 처리"""
import json
from io import BytesIO

import pytest
from PIL import Image

from app.models.passes.membership import MembershipPass
from app.models.passes.pt import PTPass
from app.models.registrations.member import Member
from app.services import broj as broj_service


def _tiny_jpeg() -> bytes:
    img = Image.new("RGB", (10, 10), color="white")
    out = BytesIO()
    img.save(out, format="JPEG")
    return out.getvalue()


_TINY_JPEG = _tiny_jpeg()


def _member_payload(branch, mp, **overrides):
    p = {
        "branch_id": str(branch.id),
        "membership_pass_id": str(mp.id),
        "name": "김화순", "gender": "M", "birth_date": "1995-09-03",
        "phone": "01012345678", "address": "전남 화순",
        "referral": "NAVER", "payment_method": "CARD",
        "final_price": 100000,
        "start_date": "2026-06-12", "end_date": "2026-07-12",
        "motivation": "WEIGHT_LOSS", "agreed_terms": True,
    }
    p.update(overrides)
    return p


@pytest.fixture
def broj_face_branch(db):
    """화순점 - broj_enabled + broj_face_enabled"""
    from app.models.branch import Branch
    b = Branch(
        name="화순점", phone="050-1234-5678",
        broj_enabled=True,
        broj_face_enabled=True,
    )
    db.add(b); db.commit(); db.refresh(b)
    return b


class TestCreateMemberBrojFace:

    def test_branch_without_face_400(self, client, db, broj_face_branch):
        """화순점 + face_image 없으면 400"""
        mp = MembershipPass(
            branch_id=broj_face_branch.id, name="1개월",
            cash_price=1, card_price=1,
        )
        db.add(mp); db.commit(); db.refresh(mp)

        res = client.post(
            "/members",
            files={"payload": (None, json.dumps(
                _member_payload(broj_face_branch, mp),
            ))},
        )
        assert res.status_code == 400
        assert "얼굴 사진" in res.json()["detail"]

    def test_with_face_success(self, client, db, broj_face_branch):
        """face 첨부 → 성공, broj_id 박힘"""
        mp = MembershipPass(
            branch_id=broj_face_branch.id, name="1개월",
            cash_price=1, card_price=1,
        )
        db.add(mp); db.commit(); db.refresh(mp)

        res = client.post(
            "/members",
            data={"payload": json.dumps(_member_payload(
                broj_face_branch, mp, phone="01088990010",
            ))},
            files={"face_image": ("face.jpg", _TINY_JPEG, "image/jpeg")},
        )
        assert res.status_code == 201, res.text
        member = db.query(Member).filter(
            Member.phone == "01088990010",
        ).first()
        assert member.broj_id == "broj-test-id"
        assert member.broj_face_registered is True

    def test_face_failure_blocks_signup(
        self, client, db, broj_face_branch, monkeypatch,
    ):
        """브로제이 얼굴 실패 → 400 + HiFIS row 없음"""
        def fail(**kw):
            raise broj_service.BrojSyncError(
                "얼굴 인증에 실패했습니다. 정면에서 얼굴이 잘 보이게 다시 찍어주세요.",
            )
        monkeypatch.setattr(
            "app.services.broj.register_member_with_face_sync", fail,
        )

        mp = MembershipPass(
            branch_id=broj_face_branch.id, name="1개월",
            cash_price=1, card_price=1,
        )
        db.add(mp); db.commit(); db.refresh(mp)

        res = client.post(
            "/members",
            data={"payload": json.dumps(_member_payload(
                broj_face_branch, mp, phone="01088990011",
            ))},
            files={"face_image": ("face.jpg", _TINY_JPEG, "image/jpeg")},
        )
        assert res.status_code == 400
        assert "얼굴 인증" in res.json()["detail"]
        assert db.query(Member).filter(
            Member.phone == "01088990011",
        ).first() is None

    def test_broj_only_no_face_async(self, client, db, branch):
        """broj_enabled=True지만 face_enabled=False → 기존 async 흐름 (face 불필요)"""
        branch.broj_enabled = True
        # broj_face_enabled 디폴트 False
        db.commit()
        mp = MembershipPass(
            branch_id=branch.id, name="1개월", cash_price=1, card_price=1,
        )
        db.add(mp); db.commit(); db.refresh(mp)

        res = client.post(
            "/members",
            json=_member_payload(branch, mp, phone="01088990012"),
        )
        assert res.status_code == 201
        # broj_id 안 박힘 (async, 응답엔 안 반영)
        m = db.query(Member).filter(Member.phone == "01088990012").first()
        assert m.broj_face_registered is None


class TestCreatePTBrojFace:

    def test_pt_with_face_success(self, client, db, broj_face_branch):
        pp = PTPass(
            branch_id=broj_face_branch.id, name="PT 10회",
            cash_price=1, card_price=1,
        )
        db.add(pp); db.commit(); db.refresh(pp)

        payload = {
            "branch_id": str(broj_face_branch.id),
            "pt_pass_id": str(pp.id),
            "name": "PT화순", "gender": "M", "birth_date": "1995-09-03",
            "phone": "01088990020", "address": "전남 화순",
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
        from app.models.registrations.pt_application import PTApplication
        app = db.query(PTApplication).filter(
            PTApplication.phone == "01088990020",
        ).first()
        assert app.broj_id == "broj-test-id"
        assert app.broj_face_registered is True
