"""다짐(Dagym) 자동 회원 등록 - HiFIS 회원가입 후 BackgroundTasks로 호출.

첨단점·동광주점 대상 (현재 동광주점만 활성). Branch.dajim_enabled=True인 지점만 동작.
GraphQL 기반:
- 로그인: 평문 비번 → SHA-256 hex 변환 → mutation Login → token (JWT)
- 회원 등록: mutation CreateManagerMember + headers (authorization, app-type, x-gym-id)
- 응답 GraphQL은 에러도 HTTP 200으로 옴 → 응답 body의 errors 필드 반드시 검사

토큰은 메모리 캐싱. 401/403 응답 시 재로그인 후 재시도 1회.
실패해도 HiFIS는 정상 동작 (best-effort, 로그만).

HiFIS → 다짐 매핑:
- name = 회원명
- phone = 하이픈 포함 형식 (010-1234-5678) ← 브로제이는 하이픈 없음, 다짐은 하이픈 유지
- gender = 'M' / 'F'
- birthday = 'YYYY-MM-DD' 문자열 ← 브로제이는 ms timestamp, 다짐은 문자열
- address = 주소
"""
import hashlib
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.models.registrations.member import Member
from app.utils.masking import mask_phone

logger = logging.getLogger(__name__)

_GRAPHQL_URL = "https://www.dagym-manager.com/api/graphql"

# 토큰 메모리 캐시 - 401/403 시 _get_token(force_refresh=True)로 재로그인
_cached_token: str | None = None

_LOGIN_QUERY = """mutation Login($email: String!, $password: String!) {
  loginAccount(email: $email, password: $password) {
    status
    token
    email
    name
    profilePhoto
    __typename
  }
}"""

_CREATE_MEMBER_QUERY = """mutation CreateManagerMember($input: MemberCreateInput!) {
  managerMembers {
    create(input: $input) {
      id
      name
      phone
      gender
      birthday
      address
      createdAt
      totalPaymentAmount
      __typename
    }
    __typename
  }
}"""


def _sha256_hex(text: str) -> str:
    """평문 → SHA-256 16진수 문자열 (다짐 로그인 비번 형식)"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _format_phone_dashed(phone: str) -> str:
    """다짐 phone 형식: 하이픈 포함. 입력이 11자리 숫자면 010-xxxx-xxxx로.

    HiFIS DB는 정규화된 11자리(01012345678) 저장이라 변환 필요.
    """
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 11:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    # 기타 형식은 원본 그대로 - 다짐이 거부할 수도 있지만 로그로 확인
    return phone


def _login(client: httpx.Client) -> str | None:
    """다짐 로그인 → token (JWT). 실패 시 None.

    GraphQL이라 HTTP 200이어도 errors 필드 있으면 실패.
    """
    payload = {
        "operationName": "Login",
        "query": _LOGIN_QUERY,
        "variables": {
            "email": settings.DAJIM_LOGIN_EMAIL,
            "password": _sha256_hex(settings.DAJIM_LOGIN_PW),
        },
    }
    try:
        resp = client.post(
            _GRAPHQL_URL,
            json=payload,
            headers={
                "app-type": "managerPC",
                "content-type": "application/json",
            },
        )
        if resp.status_code >= 400:
            logger.error(
                "다짐 로그인 HTTP 에러: status=%s, body=%s",
                resp.status_code, resp.text[:300],
            )
            return None
        body = resp.json()
        if "errors" in body:
            logger.error("다짐 로그인 GraphQL 에러: %s", body["errors"])
            return None
        login_result = (body.get("data") or {}).get("loginAccount") or {}
        if login_result.get("status") != "SUCCESS":
            logger.error(
                "다짐 로그인 status 비정상: %s, body=%s",
                login_result.get("status"), body,
            )
            return None
        token = login_result.get("token")
        if not token:
            logger.error("다짐 로그인 응답에 token 없음: %s", body)
            return None
        logger.info("다짐 로그인 성공 - 토큰 캐시 갱신")
        return token
    except Exception as e:
        logger.error("다짐 로그인 예외: %s", e)
        return None


def _get_token(client: httpx.Client, force_refresh: bool = False) -> str | None:
    """캐시된 토큰 반환. 없거나 force_refresh면 재로그인."""
    global _cached_token
    if force_refresh or _cached_token is None:
        _cached_token = _login(client)
    return _cached_token


def register_member(member: Member) -> None:
    """HiFIS 회원을 다짐에 자동 등록.

    BackgroundTasks로 호출되므로 실패해도 throw 안 함 (best-effort).
    HiFIS DB·메인 흐름은 영향 없음. 실패하면 로그만 남음.
    """
    if (
        not settings.DAJIM_LOGIN_EMAIL
        or not settings.DAJIM_LOGIN_PW
        or not settings.DAJIM_GYM_ID
    ):
        logger.warning(
            "다짐 설정 미흡 (LOGIN_EMAIL·PW·GYM_ID 중 비어있음) → 등록 스킵",
        )
        return

    input_dict: dict[str, Any] = {
        "name": member.name,
        "phone": _format_phone_dashed(member.phone),
        "address": member.address or "",
    }
    # 성별·생일은 NULL일 수 있음 (마이그 회원). 있을 때만 input에 추가
    if member.gender:
        input_dict["gender"] = member.gender
    if member.birth_date:
        input_dict["birthday"] = member.birth_date.isoformat()  # YYYY-MM-DD

    payload = {
        "operationName": "CreateManagerMember",
        "query": _CREATE_MEMBER_QUERY,
        "variables": {"input": input_dict},
    }

    with httpx.Client(timeout=15.0) as client:
        token = _get_token(client)
        if token is None:
            logger.error(
                "다짐 토큰 못 받음 → 등록 스킵: member_id=%s", member.id,
            )
            return

        for attempt in (1, 2):
            try:
                resp = client.post(
                    _GRAPHQL_URL,
                    json=payload,
                    headers={
                        "authorization": token,  # Bearer 없이 토큰만 (다짐 방식)
                        "app-type": "managerPC",
                        "x-gym-id": settings.DAJIM_GYM_ID,
                        "content-type": "application/json",
                    },
                )
                # 토큰 만료 - 첫 시도면 재로그인 후 재시도
                if resp.status_code in (401, 403) and attempt == 1:
                    logger.info(
                        "다짐 토큰 만료(%s) - 재로그인 후 재시도",
                        resp.status_code,
                    )
                    token = _get_token(client, force_refresh=True)
                    if token is None:
                        return
                    continue
                if resp.status_code >= 400:
                    logger.error(
                        "다짐 회원 등록 HTTP 실패: member_id=%s, status=%s, body=%s",
                        member.id, resp.status_code, resp.text[:500],
                    )
                    return

                body = resp.json()
                # GraphQL errors 검사 - 인증 만료가 errors로 올 수도 있어서 재시도 조건 확장
                if "errors" in body:
                    err_msg = str(body["errors"])
                    if attempt == 1 and (
                        "unauthorized" in err_msg.lower()
                        or "token" in err_msg.lower()
                    ):
                        logger.info("다짐 GraphQL 인증 에러 - 재로그인 후 재시도")
                        token = _get_token(client, force_refresh=True)
                        if token is None:
                            return
                        continue
                    logger.error(
                        "다짐 회원 등록 GraphQL 에러: member_id=%s, errors=%s",
                        member.id, err_msg[:500],
                    )
                    return

                created = (
                    ((body.get("data") or {}).get("managerMembers") or {})
                    .get("create")
                ) or {}
                created_id = created.get("id")
                if created_id:
                    logger.info(
                        "다짐 회원 등록 성공: member_id=%s, name=%s, phone=%s, "
                        "dagym_id=%s",
                        member.id, member.name,
                        mask_phone(member.phone), created_id,
                    )
                else:
                    logger.error(
                        "다짐 회원 등록 응답 비정상 (id 없음): member_id=%s, body=%s",
                        member.id, str(body)[:500],
                    )
                return
            except Exception as e:
                logger.error(
                    "다짐 회원 등록 예외: member_id=%s, error=%s",
                    member.id, e,
                )
                return
