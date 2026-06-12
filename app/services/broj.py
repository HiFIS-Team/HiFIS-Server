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
_PROFILE_IMAGE_URL = "https://brojserver.broj.co.kr/BroJServer/api/jcustomer/profile-image/{jgjm_key}"
_FACEID_ADD_URL = "https://brojserver.broj.co.kr/BroJServer/jmember/faceid/add"
_DELETE_MEMBER_URL = "https://brojserver.broj.co.kr/BroJServer/v1/admin/groups/{jgroup_key}/group-members"

_S3_BUCKET = "broj-contents"
_S3_REGION = "ap-northeast-2"


class BrojSyncError(Exception):
    """동기 브로제이 호출 실패 - 라우터에서 400으로 변환되어 가입 차단.

    얼굴 인증 실패·브로제이 응답 불량 등 회원가입 막아야 할 시나리오에서 raise.
    """

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


# === Sync 흐름 (얼굴 등록 시 사용. 실패 시 BrojSyncError raise → 가입 차단) ===

def _build_broj_payload(
    name: str, phone: str, address: str, gender: str | None,
    birth_date, motivation: str | None, referral: str | None,
    agreed_marketing: bool,
) -> dict:
    """HiFIS 데이터 → 브로제이 customer create input"""
    payload: dict[str, Any] = {
        "name": name,
        "phone_number": phone,
        "address": address or "",
        "allowed_send_sms": bool(agreed_marketing),
        "attendance_number": "0000",
        "exercise_purpose": _MOTIVATION_TO_BROJ.get(motivation or "", "DIET"),
        "visit_route": _REFERRAL_TO_BROJ.get(referral or "", "SNS"),
        "tag_keys": [],
        "jgma_jgroup_agree_dttm": _now_gmt_str(),
        "jgma_jgroup_marketing_agree_dttm": _now_gmt_str(),
    }
    if gender:
        payload["sex"] = gender
    if birth_date:
        payload["birthday"] = _date_to_ms(birth_date)
    return payload


def _create_member_sync(
    client: httpx.Client, token: str, payload: dict,
) -> str:
    """브로제이 회원 생성 + jgjm_key 반환. 실패 시 BrojSyncError.

    응답 형태: {"message": "success", "result": <jgjm_key int>, ...}
    """
    resp = client.post(
        _REGISTER_URL,
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Broj-Jgroup-Access-Token": settings.BROJ_JGROUP_TOKEN,
        },
    )
    if resp.status_code >= 400:
        raise BrojSyncError(
            f"브로제이 회원 생성 HTTP {resp.status_code}: {resp.text[:200]}",
        )
    body = resp.json()
    # 응답 형태: {"message": "success", "result": <jgjm_key int>, "events": [], "_links": {...}}
    jgjm_key = body.get("result")
    if not isinstance(jgjm_key, (int, str)) or not jgjm_key:
        raise BrojSyncError(f"브로제이 회원 응답 형식 이상: {body}")
    return str(jgjm_key)


def _upload_face_to_s3(
    jgroup_key: str, jgjm_key: str, face_jpeg: bytes,
) -> str:
    """boto3로 broj-contents 버킷에 PUT - 파일명(UUID) 반환"""
    import uuid as _uuid

    import boto3

    if not (
        settings.BROJ_AWS_ACCESS_KEY_ID
        and settings.BROJ_AWS_SECRET_ACCESS_KEY
    ):
        raise BrojSyncError("브로제이 AWS 키가 설정되지 않았습니다.")

    filename = f"{_uuid.uuid4()}.png"
    key = f"jgroup/{jgroup_key}/member/{jgjm_key}/{filename}"
    s3 = boto3.client(
        "s3",
        region_name=_S3_REGION,
        aws_access_key_id=settings.BROJ_AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.BROJ_AWS_SECRET_ACCESS_KEY,
    )
    try:
        s3.put_object(
            Bucket=_S3_BUCKET, Key=key,
            Body=face_jpeg, ContentType="image/png", ACL="private",
        )
    except Exception as e:
        raise BrojSyncError(f"브로제이 S3 PUT 실패: {e}") from e
    return filename


def _patch_profile_image(
    client: httpx.Client, token: str, jgjm_key: str, filename: str,
) -> None:
    """PATCH /jcustomer/profile-image/{jgjm_key} - 프로필 사진 갱신"""
    resp = client.patch(
        _PROFILE_IMAGE_URL.format(jgjm_key=jgjm_key),
        json={"profile_image_name": filename},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Broj-Jgroup-Access-Token": settings.BROJ_JGROUP_TOKEN,
        },
    )
    if resp.status_code >= 400:
        raise BrojSyncError(
            f"브로제이 profile-image HTTP {resp.status_code}: {resp.text[:200]}",
        )


def _delete_member_sync(
    client: httpx.Client, token: str, jgjm_key: str,
) -> None:
    """브로제이 회원 삭제 - face 등록 실패 시 cleanup용. best-effort.

    실패해도 raise 안 함 (로그만). 호출자는 원래의 BrojSyncError를 그대로 던짐.
    """
    try:
        resp = client.request(
            "DELETE",
            _DELETE_MEMBER_URL.format(jgroup_key=settings.BROJ_JGROUP_KEY),
            json={"group_member_keys": [int(jgjm_key)]},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Broj-Jgroup-Access-Token": settings.BROJ_JGROUP_TOKEN,
            },
        )
        if 200 <= resp.status_code < 300:
            logger.info("브로제이 cleanup 삭제 성공: jgjm_key=%s", jgjm_key)
        else:
            logger.error(
                "브로제이 cleanup 삭제 실패: jgjm_key=%s, status=%s, body=%s",
                jgjm_key, resp.status_code, resp.text[:200],
            )
    except Exception as e:
        logger.error(
            "브로제이 cleanup 예외: jgjm_key=%s, error=%s", jgjm_key, e,
        )


def _register_face_sync(
    client: httpx.Client, token: str, jgjm_key: str, filename: str,
) -> None:
    """POST /jmember/faceid/add - 얼굴 인증 등록.

    브로제이가 S3에서 사진 읽어 얼굴 검출. 얼굴 없는 사진(예: 단색)이면
    result=false + 'Faces not indexed.' → BrojSyncError raise.
    """
    resp = client.post(
        _FACEID_ADD_URL,
        data={"jgjm_key": jgjm_key, "filename": filename},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Broj-Jgroup-Access-Token": settings.BROJ_JGROUP_TOKEN,
        },
    )
    if resp.status_code >= 400:
        raise BrojSyncError(
            f"브로제이 faceid/add HTTP {resp.status_code}: {resp.text[:200]}",
        )
    body = resp.json()
    inner = body.get("result") or {}
    if inner.get("result") is False:
        # 얼굴 인식 실패 케이스 (Faces not indexed 등) - 사용자 친화 메시지
        msg = inner.get("message") or ""
        raise BrojSyncError(
            "얼굴 인증에 실패했습니다. 정면에서 얼굴이 잘 보이게 다시 찍어주세요."
            + (f" ({msg})" if msg else ""),
        )


def register_member_with_face_sync(
    name: str, phone: str, address: str,
    gender: str | None, birth_date,
    motivation: str | None, referral: str | None,
    agreed_marketing: bool,
    face_jpeg: bytes,
) -> tuple[str, bool]:
    """브로제이 동기 등록 + 얼굴 등록 - 화순점 회원·PT 신청 라우터에서 호출.

    반환: (broj_id, face_registered)
    실패 시 BrojSyncError. (cleanup API 미발견 → 브로제이 잔존 회원 가능)
    """
    if not (settings.BROJ_LOGIN_ID and settings.BROJ_JGROUP_TOKEN):
        raise BrojSyncError("브로제이 환경변수가 비어있습니다.")
    if not settings.BROJ_JGROUP_KEY:
        raise BrojSyncError("BROJ_JGROUP_KEY가 설정되지 않았습니다.")
    if not face_jpeg:
        raise BrojSyncError("얼굴 이미지가 비어있습니다.")

    payload = _build_broj_payload(
        name, phone, address, gender, birth_date,
        motivation, referral, agreed_marketing,
    )
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        token = _get_token(client)
        if token is None:
            raise BrojSyncError("브로제이 로그인 실패")

        # 1. 회원 생성 (토큰 만료 시 1회 재시도)
        jgjm_key: str | None = None
        for attempt in (1, 2):
            try:
                jgjm_key = _create_member_sync(client, token, payload)
                break
            except BrojSyncError as e:
                if attempt == 1 and "401" in str(e):
                    token = _get_token(client, force_refresh=True)
                    if token is None:
                        raise BrojSyncError("브로제이 재로그인 실패")
                    continue
                raise
        assert jgjm_key
        jgroup_key = settings.BROJ_JGROUP_KEY

        # 2. S3 PUT → 3. PATCH profile-image → 4. POST faceid/add
        # 실패 시 cleanup: 1번에서 만든 브로제이 회원 삭제 (orphan 방지)
        try:
            filename = _upload_face_to_s3(jgroup_key, jgjm_key, face_jpeg)
            _patch_profile_image(client, token, jgjm_key, filename)
            _register_face_sync(client, token, jgjm_key, filename)
        except BrojSyncError:
            _delete_member_sync(client, token, jgjm_key)
            raise

        logger.info(
            "브로제이 동기 등록 완료: jgjm_key=%s, name=%s, phone=%s",
            jgjm_key, name, mask_phone(phone),
        )
        return jgjm_key, True
