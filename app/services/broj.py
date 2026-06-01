"""브로제이(BroJ) 자동 회원 등록 - HiFIS 회원가입 후 BackgroundTasks로 호출.

화순점만 사용 중. Branch.broj_enabled=True인 지점만 동작.
- 로그인 토큰은 모듈 전역 캐싱 (만료 401 시 재로그인 후 재시도 1회)
- JGROUP_TOKEN은 .env (사장님이 브로제이 브라우저 네트워크탭에서 복사해 갱신)
- 실패해도 HiFIS는 정상 동작 (try/except로 흡수, 로그만)
- HiFIS enum → 브로제이 enum 매핑은 단순화 (대부분 DIET·SNS 디폴트) -
  통합 회원관리는 브로제이에서 하니까 정확한 매핑보다 등록 자체 성공이 우선
"""
import datetime
import logging
import time
from typing import Any

import httpx

from app.core.config import settings
from app.models.registrations.member import Member
from app.utils.masking import mask_phone

logger = logging.getLogger(__name__)

_LOGIN_URL = "https://brojserver.broj.co.kr/BroJServer/joauth/login"
_REGISTER_URL = "https://brojserver.broj.co.kr/BroJServer/api/jgroup/customer"

# 메모리 토큰 캐시 - 만료(401) 시 _get_token(force_refresh=True)로 재로그인
_cached_token: str | None = None

# HiFIS Motivation → BroJ exercise_purpose - 일단 DIET 디폴트 (브로제이 enum 정확히 모름)
_MOTIVATION_TO_BROJ = {
    "WEIGHT_LOSS": "DIET",
    "MUSCLE_GAIN": "DIET",
    "HEALTH_IMPROVEMENT": "DIET",
    "STRESS_RELIEF": "DIET",
    "APPEARANCE": "DIET",
    "RECOMMENDATION": "DIET",
    "INJURY_PREVENTION": "DIET",
    "POSTURE_CORRECTION": "DIET",
}

# HiFIS Referral → BroJ visit_route - 일단 SNS 디폴트
_REFERRAL_TO_BROJ = {
    "NAVER": "SNS",
    "BLOG": "SNS",
    "INSTAGRAM": "SNS",
    "FLYER": "SNS",
    "BANNER": "SNS",
    "FRIEND": "SNS",
    "OTHER": "SNS",
}


def _now_gmt_str() -> str:
    """현재 시각 GMT 문자열 (예: 'Thu, 01 Jun 2026 04:23:45 GMT')"""
    return time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())


def _date_to_ms(d: datetime.date | None) -> int | None:
    """date → UTC 자정 기준 ms timestamp"""
    if d is None:
        return None
    dt = datetime.datetime(d.year, d.month, d.day, tzinfo=datetime.timezone.utc)
    return int(dt.timestamp() * 1000)


def _login(client: httpx.Client) -> str | None:
    """브로제이 로그인 → access_token. 실패 시 None."""
    try:
        resp = client.post(
            _LOGIN_URL,
            data={
                "member_id": settings.BROJ_LOGIN_ID,
                "member_password": settings.BROJ_LOGIN_PW,
            },
        )
        if resp.status_code >= 400:
            logger.error(
                "브로제이 로그인 실패: status=%s, body=%s",
                resp.status_code, resp.text[:200],
            )
            return None
        token = (resp.json().get("result") or {}).get("access_token")
        if not token:
            logger.error(
                "브로제이 로그인 응답에 access_token 없음: %s",
                resp.json(),
            )
            return None
        logger.info("브로제이 로그인 성공 - 토큰 캐시 갱신")
        return token
    except Exception as e:
        logger.error("브로제이 로그인 예외: %s", e)
        return None


def _get_token(client: httpx.Client, force_refresh: bool = False) -> str | None:
    """캐시된 토큰 반환. 없거나 force_refresh면 재로그인."""
    global _cached_token
    if force_refresh or _cached_token is None:
        _cached_token = _login(client)
    return _cached_token


def register_member(member: Member) -> None:
    """HiFIS 회원을 브로제이에 자동 등록.

    BackgroundTasks로 호출되니까 실패해도 호출자에 throw 안 함 (best-effort).
    HiFIS DB·메인 흐름은 영향 없음. 실패하면 로그만 남음.
    """
    if not settings.BROJ_LOGIN_ID or not settings.BROJ_JGROUP_TOKEN:
        logger.warning(
            "브로제이 설정 미흡 (LOGIN_ID 또는 JGROUP_TOKEN 비어있음) → 등록 스킵",
        )
        return

    payload: dict[str, Any] = {
        "name": member.name,
        "phone_number": member.phone,
        "address": member.address or "",
        "allowed_send_sms": bool(member.agreed_marketing),
        # HiFIS에는 출석번호 개념 없음 → 디폴트 (브로제이 측에서 자동 할당이면 무시됨)
        "attendance_number": "0000",
        "exercise_purpose": _MOTIVATION_TO_BROJ.get(
            member.motivation or "", "DIET",
        ),
        "visit_route": _REFERRAL_TO_BROJ.get(member.referral or "", "SNS"),
        "tag_keys": [],
        "jgma_jgroup_agree_dttm": _now_gmt_str(),
        "jgma_jgroup_marketing_agree_dttm": _now_gmt_str(),
    }
    # 성별·생일은 NULL일 수 있음 (마이그 회원). 있을 때만 payload에 추가
    if member.gender:
        payload["sex"] = member.gender
    if member.birth_date:
        payload["birthday"] = _date_to_ms(member.birth_date)

    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        token = _get_token(client)
        if token is None:
            logger.error(
                "브로제이 토큰 못 받음 → 등록 스킵: member_id=%s", member.id,
            )
            return

        for attempt in (1, 2):
            try:
                resp = client.post(
                    _REGISTER_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-Broj-Jgroup-Access-Token": settings.BROJ_JGROUP_TOKEN,
                    },
                )
                # 토큰 만료 - 첫 시도면 재로그인 후 재시도
                if resp.status_code == 401 and attempt == 1:
                    logger.info("브로제이 토큰 만료(401) - 재로그인 후 재시도")
                    token = _get_token(client, force_refresh=True)
                    if token is None:
                        return
                    continue
                if 200 <= resp.status_code < 300:
                    logger.info(
                        "브로제이 회원 등록 성공: member_id=%s, name=%s, phone=%s",
                        member.id, member.name, mask_phone(member.phone),
                    )
                    return
                logger.error(
                    "브로제이 회원 등록 실패: member_id=%s, status=%s, body=%s",
                    member.id, resp.status_code, resp.text[:300],
                )
                return
            except Exception as e:
                logger.error(
                    "브로제이 회원 등록 예외: member_id=%s, error=%s",
                    member.id, e,
                )
                return
