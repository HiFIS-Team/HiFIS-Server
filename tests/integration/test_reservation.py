"""예약 통합 테스트 - POST /reservations, GET/DELETE /admin/reservations"""
from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.models.messaging.message import Message
from app.models.registrations.reservation import Reservation


def _reservation_payload(branch, **overrides):
    """필수 필드 다 채운 예약 payload"""
    payload = {
        "branch_id": str(branch.id),
        "name": "김방문",
        "phone": "01012345678",
        "visit_date": str(date.today() + timedelta(days=3)),
    }
    payload.update(overrides)
    return payload


class TestCreateReservation:

    def test_create_reservation(self, client, db, branch):
        """예약 신청 → 201 + DB row 1개"""
        res = client.post("/reservations", json=_reservation_payload(branch))
        assert res.status_code == 201, res.text
        assert res.json()["name"] == "김방문"

        row = db.query(Reservation).filter(Reservation.phone == "01012345678").first()
        assert row is not None
        assert row.branch_id == branch.id

    def test_create_reservation_logs_message(self, client, db, branch):
        """예약 신청 시 RESERVATION_CONFIRM 알림톡 이력 저장 (Solapi는 mock)"""
        res = client.post("/reservations", json=_reservation_payload(branch))
        assert res.status_code == 201

        msg = db.query(Message).filter(Message.recipient == "01012345678").first()
        assert msg is not None
        assert msg.trigger_type == "RESERVATION_CONFIRM"
        assert msg.status == "SUCCESS"

    def test_create_reservation_nonexistent_branch_404(self, client):
        """존재하지 않는 지점 → 404"""
        payload = {
            "branch_id": str(uuid4()),
            "name": "김방문",
            "phone": "01012345678",
            "visit_date": str(date.today() + timedelta(days=3)),
        }
        res = client.post("/reservations", json=payload)
        assert res.status_code == 404

    def test_create_reservation_past_visit_date_422(self, client, branch):
        """방문 예정일이 과거 → 422 (Pydantic validation)"""
        res = client.post(
            "/reservations",
            json=_reservation_payload(
                branch, visit_date=str(date.today() - timedelta(days=1)),
            ),
        )
        assert res.status_code == 422


class TestListReservationPermissions:

    @pytest.fixture
    def two_branch_reservations(self, db, branch, branch_other):
        """화순점/첨단점 각각 예약 1건"""
        today = date.today()
        r_a = Reservation(
            branch_id=branch.id, name="화순예약",
            phone="01011111111", visit_date=today,
        )
        r_b = Reservation(
            branch_id=branch_other.id, name="첨단예약",
            phone="01022222222", visit_date=today,
        )
        db.add_all([r_a, r_b]); db.commit()
        return {"r_a": r_a, "r_b": r_b}

    def test_super_admin_sees_all(self, client, auth_super, two_branch_reservations):
        """SUPER_ADMIN은 전 지점 예약을 다 봄"""
        res = client.get("/admin/reservations", headers=auth_super)
        assert res.status_code == 200
        names = {r["name"] for r in res.json()["items"]}
        assert {"화순예약", "첨단예약"} <= names

    def test_fc_sees_only_own_branch(self, client, auth_fc, two_branch_reservations):
        """FC는 branch_id 안 줘도 자기 지점만 (권한 누수 회귀 방지)"""
        res = client.get("/admin/reservations", headers=auth_fc)
        assert res.status_code == 200
        names = {r["name"] for r in res.json()["items"]}
        assert "화순예약" in names
        assert "첨단예약" not in names

    def test_no_auth_401(self, client):
        res = client.get("/admin/reservations")
        assert res.status_code == 401


class TestDeleteReservation:

    @pytest.fixture
    def reservation(self, db, branch):
        r = Reservation(
            branch_id=branch.id, name="삭제대상",
            phone="01033334444", visit_date=date.today(),
        )
        db.add(r); db.commit(); db.refresh(r)
        return r

    def test_delete_reservation(self, client, db, auth_super, reservation):
        """예약 삭제 → 204 + DB row 제거"""
        res = client.delete(
            f"/admin/reservations/{reservation.id}", headers=auth_super,
        )
        assert res.status_code == 204
        assert db.query(Reservation).filter(
            Reservation.id == reservation.id
        ).first() is None

    def test_fc_cannot_delete_other_branch_404(
        self, client, db, auth_fc, branch_other,
    ):
        """FC가 타 지점 예약 삭제 → 404"""
        r = Reservation(
            branch_id=branch_other.id, name="타지점예약",
            phone="01055556666", visit_date=date.today(),
        )
        db.add(r); db.commit(); db.refresh(r)
        res = client.delete(f"/admin/reservations/{r.id}", headers=auth_fc)
        assert res.status_code == 404

    def test_delete_nonexistent_404(self, client, auth_super):
        res = client.delete(
            f"/admin/reservations/{uuid4()}", headers=auth_super,
        )
        assert res.status_code == 404
