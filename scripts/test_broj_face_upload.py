"""브로제이 얼굴 등록 풀 흐름 테스트 - boto3 S3 PUT + faceid/add.

⚠️ 실제 브로제이 회원에 영향 가는 호출. 테스트 회원 ID만 사용할 것.

흐름:
1. 로컬 JPEG 준비 (Pillow로 가짜 사진 만듦)
2. boto3로 broj-contents S3 버킷에 PUT
3. POST /jmember/faceid/add 호출
4. 응답 확인 (브로제이 어드민에서 사진 바뀌었는지 직접 보기)
"""
import sys
import uuid
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import boto3  # noqa: E402
import httpx  # noqa: E402
from PIL import Image  # noqa: E402

from app.core.config import settings  # noqa: E402


# ⚠️ 너 테스트 회원 ID + jgroup ID
TEST_MEMBER_ID = "1104335899"
TEST_JGROUP_ID = "24364928"

# 브로제이 IAM 키는 .env에서 (절대 하드코딩 X - GitHub Secret Scanning 차단됨)
BROJ_AWS_ACCESS_KEY = settings.BROJ_AWS_ACCESS_KEY_ID
BROJ_AWS_SECRET_KEY = settings.BROJ_AWS_SECRET_ACCESS_KEY

BUCKET = "broj-contents"
REGION = "ap-northeast-2"


def make_test_jpeg() -> bytes:
    """Pillow로 빨간 200x200 JPEG 생성"""
    img = Image.new("RGB", (200, 200), color="red")
    out = BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue()


def main():
    # 1. 로그인
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            "https://brojserver.broj.co.kr/BroJServer/joauth/login",
            data={
                "member_id": settings.BROJ_LOGIN_ID,
                "member_password": settings.BROJ_LOGIN_PW,
            },
        )
        token = r.json()["result"]["access_token"]
        print(f"✅ login OK: {token[:30]}...")

        # 2. 파일명 생성 + S3 PUT
        filename = f"{uuid.uuid4()}.png"
        key = f"jgroup/{TEST_JGROUP_ID}/member/{TEST_MEMBER_ID}/{filename}"
        print(f"📤 S3 PUT → s3://{BUCKET}/{key}")

        s3 = boto3.client(
            "s3",
            region_name=REGION,
            aws_access_key_id=BROJ_AWS_ACCESS_KEY,
            aws_secret_access_key=BROJ_AWS_SECRET_KEY,
        )
        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=make_test_jpeg(),
            ContentType="image/png",
            ACL="private",
        )
        print("✅ S3 PUT 성공")

        # 3. PATCH /jcustomer/profile-image/{member_id} - 프로필 사진 갱신 (표시용)
        r = client.patch(
            f"https://brojserver.broj.co.kr/BroJServer/api/jcustomer/profile-image/{TEST_MEMBER_ID}",
            json={"profile_image_name": filename},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Broj-Jgroup-Access-Token": settings.BROJ_JGROUP_TOKEN,
            },
        )
        print(f"📡 PATCH /profile-image status: {r.status_code}")
        print(f"   body: {r.text}")
        print()

        # 4. POST /faceid/add - 얼굴 인증 등록 (별도 시스템)
        r = client.post(
            "https://brojserver.broj.co.kr/BroJServer/jmember/faceid/add",
            data={"jgjm_key": TEST_MEMBER_ID, "filename": filename},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Broj-Jgroup-Access-Token": settings.BROJ_JGROUP_TOKEN,
            },
        )
        print(f"📡 POST /faceid/add status: {r.status_code}")
        print(f"   body: {r.text}")
        print()
        print(f"👀 브로제이 어드민에서 {TEST_MEMBER_ID} 회원 얼굴 확인해줘 (빨간 사진이어야)")


if __name__ == "__main__":
    main()
