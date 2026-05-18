"""스키마 validator 단위 테스트 - 날짜·논리 검증 (DB 불필요)"""
from datetime import date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.schemas.registrations.member import MemberCreate, MemberUpdate
from app.schemas.registrations.pt_application import (
    PTApplicationCreate,
    PTApplicationUpdate,
)
from app.schemas.registrations.reservation import ReservationCreate

_KST = ZoneInfo("Asia/Seoul")


def _today():
    return datetime.now(_KST).date()


# === ReservationCreate ===

class TestReservationVisitDate:

    def _payload(self, **overrides):
        base = {
            "branch_id": str(uuid4()),
            "name": "김은후",
            "phone": "01012345678",
            "visit_date": _today() + timedelta(days=1),
        }
        base.update(overrides)
        return base

    def test_visit_today_ok(self):
        ReservationCreate(**self._payload(visit_date=_today()))

    def test_visit_future_ok(self):
        ReservationCreate(**self._payload(visit_date=_today() + timedelta(days=30)))

    def test_visit_past_rejected(self):
        with pytest.raises(ValidationError) as e:
            ReservationCreate(**self._payload(visit_date=_today() - timedelta(days=1)))
        assert "방문 예정일" in str(e.value)


# === MemberCreate ===

class TestMemberBirthDate:

    def _payload(self, **overrides):
        base = {
            "branch_id": str(uuid4()),
            "membership_pass_id": str(uuid4()),
            "name": "김은후",
            "gender": "M",
            "birth_date": date(1995, 9, 3),
            "phone": "01012345678",
            "address": "광주",
            "referral": "NAVER",
            "payment_method": "CARD",
            "final_price": 100000,
            "start_date": _today(),
            "end_date": _today() + timedelta(days=30),
            "motivation": "WEIGHT_LOSS",
            "agreed_terms": True,
        }
        base.update(overrides)
        return base

    def test_normal_birth_ok(self):
        MemberCreate(**self._payload())

    def test_birth_today_ok(self):
        """오늘 태어난 신생아도 통과 (의미는 없지만 sanity 통과)"""
        MemberCreate(**self._payload(birth_date=_today()))

    def test_birth_future_rejected(self):
        with pytest.raises(ValidationError) as e:
            MemberCreate(**self._payload(birth_date=_today() + timedelta(days=1)))
        assert "오늘 이후" in str(e.value)

    def test_birth_too_old_rejected(self):
        with pytest.raises(ValidationError) as e:
            MemberCreate(**self._payload(birth_date=date(1800, 1, 1)))
        assert "과거" in str(e.value)


class TestMemberPeriod:

    def _payload(self, **overrides):
        base = {
            "branch_id": str(uuid4()),
            "membership_pass_id": str(uuid4()),
            "name": "김은후",
            "gender": "M",
            "birth_date": date(1995, 9, 3),
            "phone": "01012345678",
            "address": "광주",
            "referral": "NAVER",
            "payment_method": "CARD",
            "final_price": 100000,
            "start_date": date(2026, 5, 1),
            "end_date": date(2026, 6, 1),
            "motivation": "WEIGHT_LOSS",
            "agreed_terms": True,
        }
        base.update(overrides)
        return base

    def test_start_before_end_ok(self):
        MemberCreate(**self._payload())

    def test_same_day_ok(self):
        MemberCreate(**self._payload(
            start_date=date(2026, 5, 1), end_date=date(2026, 5, 1),
        ))

    def test_end_before_start_rejected(self):
        with pytest.raises(ValidationError) as e:
            MemberCreate(**self._payload(
                start_date=date(2026, 6, 1), end_date=date(2026, 5, 1),
            ))
        assert "종료일" in str(e.value)


class TestMemberUpdatePartial:
    """부분 수정 - 둘 다 들어왔을 때만 검증"""

    def test_only_start_provided_ok(self):
        """start_date만 수정 - 검증 스킵 (DB 값과 비교는 서비스 책임)"""
        MemberUpdate(start_date=date(2026, 5, 1))

    def test_only_end_provided_ok(self):
        MemberUpdate(end_date=date(2026, 5, 1))

    def test_both_provided_consistent_ok(self):
        MemberUpdate(start_date=date(2026, 5, 1), end_date=date(2026, 6, 1))

    def test_both_provided_inconsistent_rejected(self):
        with pytest.raises(ValidationError) as e:
            MemberUpdate(start_date=date(2026, 6, 1), end_date=date(2026, 5, 1))
        assert "종료일" in str(e.value)

    def test_birth_future_in_update_rejected(self):
        with pytest.raises(ValidationError):
            MemberUpdate(birth_date=_today() + timedelta(days=1))


# === PTApplicationCreate ===

class TestPTApplicationPeriod:
    """PT 신청도 동일한 검증을 가지는지 확인 (회귀 방지)"""

    def _payload(self, **overrides):
        base = {
            "branch_id": str(uuid4()),
            "pt_pass_id": str(uuid4()),
            "name": "김은후",
            "gender": "M",
            "birth_date": date(1995, 9, 3),
            "phone": "01012345678",
            "address": "광주",
            "referral": "NAVER",
            "payment_method": "CARD",
            "final_price": 100000,
            "start_date": date(2026, 5, 1),
            "end_date": date(2026, 6, 1),
            "agreed_notice": True,
        }
        base.update(overrides)
        return base

    def test_normal_ok(self):
        PTApplicationCreate(**self._payload())

    def test_end_before_start_rejected(self):
        with pytest.raises(ValidationError):
            PTApplicationCreate(**self._payload(
                start_date=date(2026, 6, 1), end_date=date(2026, 5, 1),
            ))

    def test_birth_future_rejected(self):
        with pytest.raises(ValidationError):
            PTApplicationCreate(**self._payload(birth_date=_today() + timedelta(days=1)))


class TestPTApplicationUpdate:
    def test_both_inconsistent_rejected(self):
        with pytest.raises(ValidationError):
            PTApplicationUpdate(start_date=date(2026, 6, 1), end_date=date(2026, 5, 1))

    def test_only_start_ok(self):
        PTApplicationUpdate(start_date=date(2026, 5, 1))
