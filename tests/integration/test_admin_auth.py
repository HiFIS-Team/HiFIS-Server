"""FC 셀프 가입 / 이메일 인증 / 승인 흐름 통합 테스트"""
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.models.admin.admin import Admin
from app.models.admin.email_verification_token import EmailVerificationToken

_KST = ZoneInfo("Asia/Seoul")


def _signup_payload(branch, **overrides):
    base = {
        "email": "newfc@test.com",
        "name": "신규FC",
        "password": "fcpass1234",
        "branch_id": str(branch.id),
    }
    base.update(overrides)
    return base


def _get_token(db, email):
    """DB에서 인증 토큰 조회 (메일 mock이라 코드를 직접 가져옴)"""
    return (
        db.query(EmailVerificationToken)
        .join(Admin, EmailVerificationToken.admin_id == Admin.id)
        .filter(Admin.email == email)
        .first()
    )


class TestSignup:

    def test_signup_creates_pending_email(self, client, db, branch):
        """가입 시 PENDING_EMAIL 상태 + 6자리 인증번호 생성"""
        res = client.post("/admin/signup", json=_signup_payload(branch))
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["status"] == "PENDING_EMAIL"
        assert body["role"] == "FC"

        token = _get_token(db, "newfc@test.com")
        assert token is not None
        assert len(token.code) == 6

    def test_signup_duplicate_email_409(self, client, branch):
        client.post("/admin/signup", json=_signup_payload(branch))
        res = client.post("/admin/signup", json=_signup_payload(branch))
        assert res.status_code == 409

    def test_signup_invalid_branch_404(self, client):
        res = client.post("/admin/signup", json={
            "email": "x@test.com", "name": "x",
            "password": "fcpass1234", "branch_id": str(uuid4()),
        })
        assert res.status_code == 404


class TestVerifyEmail:

    def test_verify_correct_code(self, client, db, branch):
        client.post("/admin/signup", json=_signup_payload(branch))
        code = _get_token(db, "newfc@test.com").code
        res = client.post("/admin/verify-email", json={
            "email": "newfc@test.com", "code": code,
        })
        assert res.status_code == 200
        assert res.json()["status"] == "PENDING_APPROVAL"

    def test_verify_wrong_code_400(self, client, branch):
        client.post("/admin/signup", json=_signup_payload(branch))
        res = client.post("/admin/verify-email", json={
            "email": "newfc@test.com", "code": "000000",
        })
        assert res.status_code == 400

    def test_verify_expired_code_400(self, client, db, branch):
        client.post("/admin/signup", json=_signup_payload(branch))
        token = _get_token(db, "newfc@test.com")
        token.expires_at = datetime.now(_KST) - timedelta(minutes=1)  # 만료시킴
        db.commit()
        res = client.post("/admin/verify-email", json={
            "email": "newfc@test.com", "code": token.code,
        })
        assert res.status_code == 400


class TestApprovalFlow:

    def _signup_and_verify(self, client, db, branch):
        """가입 + 이메일 인증까지 진행 (PENDING_APPROVAL 상태로 만듦)"""
        client.post("/admin/signup", json=_signup_payload(branch))
        code = _get_token(db, "newfc@test.com").code
        client.post("/admin/verify-email", json={
            "email": "newfc@test.com", "code": code,
        })

    def test_login_before_approval_403(self, client, db, branch):
        """승인 전 로그인 시도 → 403"""
        self._signup_and_verify(client, db, branch)
        res = client.post("/admin/login", json={
            "email": "newfc@test.com", "password": "fcpass1234",
        })
        assert res.status_code == 403

    def test_pending_list_shows_verified(self, client, db, branch, auth_super):
        """이메일 인증 완료 계정이 승인 대기 목록에 표시"""
        self._signup_and_verify(client, db, branch)
        res = client.get("/admin/admins/pending", headers=auth_super)
        assert res.status_code == 200
        assert "newfc@test.com" in {a["email"] for a in res.json()}

    def test_approve_then_login_success(self, client, db, branch, auth_super):
        """승인 후 로그인 성공"""
        self._signup_and_verify(client, db, branch)
        fc = db.query(Admin).filter(Admin.email == "newfc@test.com").first()

        approve = client.post(f"/admin/admins/{fc.id}/approve", headers=auth_super)
        assert approve.status_code == 200
        assert approve.json()["status"] == "ACTIVE"

        login = client.post("/admin/login", json={
            "email": "newfc@test.com", "password": "fcpass1234",
        })
        assert login.status_code == 200
        assert "access_token" in login.json()

    def test_pending_list_requires_auth(self, client, db, branch):
        """토큰 없이 승인 대기 목록 접근 → 401"""
        self._signup_and_verify(client, db, branch)
        res = client.get("/admin/admins/pending")
        assert res.status_code == 401
