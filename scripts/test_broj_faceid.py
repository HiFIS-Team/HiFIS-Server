"""브로제이 얼굴 등록 API 탐색 - 임시 디버그 스크립트.

실제 PUT 없이 /jmember/faceid/add만 먼저 호출해서 응답 형태 확인:
- 400 file not found → S3 PUT 필수 (예상)
- 415/422/etc → 페이로드 형식 문제
- 200 → 의외로 파일명만 박아도 됨

실행: python scripts/test_broj_faceid.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from app.services.broj import _get_token  # noqa: E402
from app.core.config import settings  # noqa: E402


FACEID_ADD_URL = "https://brojserver.broj.co.kr/BroJServer/jmember/faceid/add"

# 실제 회원 ID (브로제이 어드민에서 본 거)
TEST_MEMBER_ID = "1104335899"
TEST_FILENAME = "nonexistent-test.png"


def main():
    print(f"BROJ_LOGIN_ID: {settings.BROJ_LOGIN_ID}")
    print(f"BROJ_JGROUP_TOKEN: {settings.BROJ_JGROUP_TOKEN[:20]}...")
    print()

    with httpx.Client(timeout=60.0) as client:
        token = _get_token(client)
        if token is None:
            print("❌ 로그인 실패 - .env 확인")
            return
        print(f"✅ 로그인 성공, token: {token[:30]}...")
        print()

        # POST /jmember/faceid/add 시도
        # 1. JSON body 패턴
        print("=== 시도 1: JSON body ===")
        resp = client.post(
            FACEID_ADD_URL,
            json={"jgjm_key": TEST_MEMBER_ID, "filename": TEST_FILENAME},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Broj-Jgroup-Access-Token": settings.BROJ_JGROUP_TOKEN,
            },
        )
        print(f"  status: {resp.status_code}")
        print(f"  body  : {resp.text[:500]}")
        print()

        # 2. form-urlencoded 패턴 (네트워크 탭에서 보였던 패턴과 동일)
        print("=== 시도 2: form-urlencoded ===")
        resp = client.post(
            FACEID_ADD_URL,
            data={"jgjm_key": TEST_MEMBER_ID, "filename": TEST_FILENAME},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Broj-Jgroup-Access-Token": settings.BROJ_JGROUP_TOKEN,
            },
        )
        print(f"  status: {resp.status_code}")
        print(f"  body  : {resp.text[:500]}")
        print()


if __name__ == "__main__":
    main()
