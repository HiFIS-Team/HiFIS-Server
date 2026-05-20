"""pytest 공통 fixture - DB 통합 테스트용 인프라

전략:
- 별도 테스트 DB (hifis_test) 사용
- 세션 1회: 전체 스키마 drop/create
- 테스트 1개당: 트랜잭션 wrap → rollback (데이터 오염 0)
- TestClient는 같은 세션을 사용하도록 get_db 의존성 오버라이드
- Solapi/Claude는 autouse mock (실제 외부 API 호출 안 함)
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.deps import get_db
from app.main import app
from app.models.admin.admin import Admin
from app.models.branch import Branch

# 테스트 DB URL: 기존 DATABASE_URL에서 DB 이름만 hifis_test로 교체
TEST_DATABASE_URL = settings.DATABASE_URL.rsplit("/", 1)[0] + "/hifis_test"


# === 엔진 (세션 1회) ===

@pytest.fixture(scope="session")
def engine():
    """테스트 세션 전체에서 1회 - 스키마 생성 후 yield, 종료 시 drop"""
    eng = create_engine(
        TEST_DATABASE_URL,
        connect_args={"options": "-c timezone=Asia/Seoul"},
    )
    Base.metadata.drop_all(eng)   # 이전 실패 잔해 청소
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


# === DB 세션 (테스트 1개당, 트랜잭션 rollback) ===

@pytest.fixture
def db(engine):
    """테스트별 트랜잭션 wrap - 서비스의 db.commit()은 savepoint로 처리

    테스트 끝나면 outer transaction rollback → DB 깨끗하게 유지
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    # 서비스 코드가 commit해도 outer transaction은 살아있게 (savepoint)
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# === TestClient (get_db 오버라이드해서 위 db 세션 공유) ===

@pytest.fixture
def client(db):
    """FastAPI TestClient - 같은 db 세션을 라우터/서비스에서 쓰도록 의존성 오버라이드"""
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    # with 블록 없이 생성 = lifespan 스킵 (스케줄러 안 뜸)
    yield TestClient(app)
    app.dependency_overrides.clear()


# === 외부 API mock (모든 테스트 자동 적용) ===

@pytest.fixture(autouse=True)
def mock_external_apis(monkeypatch):
    """Solapi(LMS)와 Claude(AI) 호출을 가짜로 - 실제 발송/과금 차단"""
    # Solapi send_sms: (success=True, error=None) 반환
    monkeypatch.setattr(
        "app.services.messaging.solapi.send_sms",
        lambda recipient, content, subject="": (True, None),
    )
    # message.py가 from solapi import send_sms 했다면 거기도 패치
    monkeypatch.setattr(
        "app.services.messaging.message.solapi.send_sms",
        lambda recipient, content, subject="": (True, None),
        raising=False,
    )
    # Claude: 가짜 본문 반환
    monkeypatch.setattr(
        "app.services.messaging.claude.generate_hold_body",
        lambda **kw: "테스트용 홀딩 안내 본문입니다.",
    )
    monkeypatch.setattr(
        "app.services.messaging.claude.generate_hold_cancel_body",
        lambda **kw: "테스트용 홀딩 취소 안내 본문입니다.",
    )
    # 이메일 발송 (FC 가입 인증 / 비밀번호 재설정) - admin 서비스가 import한 함수 패치
    monkeypatch.setattr(
        "app.services.admin.admin.send_verification_email",
        lambda to_email, name, code: True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.admin.admin.send_password_reset_email",
        lambda to_email, name, code: True,
        raising=False,
    )


# === 도메인 fixture (지점 / 관리자) ===

@pytest.fixture
def branch(db):
    """샘플 지점 (화순점)"""
    b = Branch(
        name="화순점",
        phone="050-1234-5678",
        naver_place_url="https://naver.me/test",
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


@pytest.fixture
def branch_other(db):
    """다른 지점 (FC 권한 테스트용)"""
    b = Branch(name="첨단점", phone="050-9999-9999")
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


@pytest.fixture
def super_admin(db):
    """SUPER_ADMIN 관리자 (전 지점 접근)"""
    a = Admin(
        email="super@test.com",
        password_hash=hash_password("test1234"),
        name="대표",
        role="SUPER_ADMIN",
        branch_id=None,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


@pytest.fixture
def fc_admin(db, branch):
    """FC 관리자 (화순점만 접근)"""
    a = Admin(
        email="fc@test.com",
        password_hash=hash_password("test1234"),
        name="FC담당자",
        role="FC",
        branch_id=branch.id,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


@pytest.fixture
def auth_super(super_admin):
    """SUPER_ADMIN 인증 헤더"""
    token = create_access_token(str(super_admin.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_fc(fc_admin):
    """FC 인증 헤더"""
    token = create_access_token(str(fc_admin.id))
    return {"Authorization": f"Bearer {token}"}
