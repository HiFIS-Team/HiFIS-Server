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


class TestDeleteAdmin:

    def test_delete_fc(self, client, db, fc_admin, auth_super):
        """FC 계정 삭제 → 204, DB에서 제거됨"""
        res = client.delete(
            f"/admin/admins/{fc_admin.id}", headers=auth_super
        )
        assert res.status_code == 204
        assert db.query(Admin).filter(Admin.id == fc_admin.id).first() is None

    def test_delete_super_admin_rejected(self, client, super_admin, auth_super):
        """SUPER_ADMIN 계정 삭제 시도 → 400 (보호)"""
        res = client.delete(
            f"/admin/admins/{super_admin.id}", headers=auth_super
        )
        assert res.status_code == 400

    def test_delete_nonexistent_404(self, client, auth_super):
        """존재하지 않는 계정 삭제 → 404"""
        res = client.delete(
            f"/admin/admins/{uuid4()}", headers=auth_super
        )
        assert res.status_code == 404

    def test_delete_requires_auth(self, client):
        """토큰 없이 삭제 시도 → 401"""
        res = client.delete(f"/admin/admins/{uuid4()}")
        assert res.status_code == 401


class TestRefreshToken:

    def _login(self, client):
        """fc_admin 로그인 → 응답 body 반환"""
        return client.post("/admin/login", json={
            "email": "fc@test.com", "password": "test1234",
        }).json()

    def test_login_returns_both_tokens(self, client, fc_admin):
        """로그인 응답에 access_token + refresh_token 둘 다 포함"""
        body = self._login(client)
        assert "access_token" in body
        assert "refresh_token" in body

    def test_refresh_issues_new_access(self, client, fc_admin):
        """refresh_token으로 새 access 발급"""
        login = self._login(client)
        res = client.post("/admin/refresh", json={
            "refresh_token": login["refresh_token"],
        })
        assert res.status_code == 200
        body = res.json()
        assert "access_token" in body
        assert "refresh_token" in body

    def test_refresh_invalid_token_401(self, client):
        """깨진 refresh token → 401"""
        res = client.post("/admin/refresh", json={
            "refresh_token": "invalid.token.value",
        })
        assert res.status_code == 401

    def test_access_token_cannot_refresh(self, client, fc_admin):
        """access token을 refresh 엔드포인트에 넣으면 → 401 (type 검증)"""
        login = self._login(client)
        res = client.post("/admin/refresh", json={
            "refresh_token": login["access_token"],
        })
        assert res.status_code == 401

    def test_refreshed_access_works(self, client, fc_admin):
        """refresh로 받은 새 access로 인증 API 호출 가능"""
        login = self._login(client)
        refreshed = client.post("/admin/refresh", json={
            "refresh_token": login["refresh_token"],
        }).json()
        res = client.get("/admin/members", headers={
            "Authorization": f"Bearer {refreshed['access_token']}",
        })
        assert res.status_code == 200

    def test_refresh_token_rejected_as_access(self, client, fc_admin):
        """refresh token으로 일반 API 호출 시도 → 401 (type 검증)"""
        login = self._login(client)
        res = client.get("/admin/members", headers={
            "Authorization": f"Bearer {login['refresh_token']}",
        })
        assert res.status_code == 401


class TestMe:

    def test_get_me(self, client, fc_admin, auth_fc):
        """본인 정보 조회"""
        res = client.get("/admin/me", headers=auth_fc)
        assert res.status_code == 200
        body = res.json()
        assert body["email"] == "fc@test.com"
        assert body["role"] == "FC"

    def test_get_me_requires_auth(self, client):
        """토큰 없이 본인 정보 조회 → 401"""
        res = client.get("/admin/me")
        assert res.status_code == 401

    def test_update_me_name(self, client, fc_admin, auth_fc):
        """본인 이름 수정"""
        res = client.patch(
            "/admin/me", headers=auth_fc, json={"name": "새이름"}
        )
        assert res.status_code == 200
        assert res.json()["name"] == "새이름"

    def test_change_password_then_login(self, client, fc_admin, auth_fc):
        """비밀번호 변경 후 새 비번으로 로그인 성공"""
        res = client.patch("/admin/me/password", headers=auth_fc, json={
            "current_password": "test1234",
            "new_password": "newpass5678",
        })
        assert res.status_code == 204

        login = client.post("/admin/login", json={
            "email": "fc@test.com", "password": "newpass5678",
        })
        assert login.status_code == 200

    def test_change_password_wrong_current_401(self, client, fc_admin, auth_fc):
        """현재 비밀번호 틀리면 → 401"""
        res = client.patch("/admin/me/password", headers=auth_fc, json={
            "current_password": "wrongpass",
            "new_password": "newpass5678",
        })
        assert res.status_code == 401
