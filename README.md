# HiFIS Server

피트니스스타 헬스장의 회원 / 개인레슨(PT) 신청 플랫폼 백엔드.

태블릿에 고정된 PWA에서 회원이 직접 작성하는 디지털 신청서, 알림톡 자동 발송, 관리자 대시보드 API를 제공합니다.

> 프론트엔드는 [별도 레포](https://github.com/) (Svelte PWA)에서 관리됩니다.

---

## 기술 스택

- **Backend** : FastAPI (Python 3.14)
- **DB** : PostgreSQL (timezone: Asia/Seoul)
- **ORM / Migration** : SQLAlchemy 2.0 + Alembic
- **인증** : 자체 JWT (bcrypt + HS256)
- **외부 API** : Solapi (LMS), Claude API (홀딩 본문)
- **테스트** : pytest (+ pytest-cov)
- **스케줄러** : APScheduler (매일 08:00 KST)

---

## Quick Start

### 1) 의존성 설치

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # 테스트 실행 시 추가
```

### 2) PostgreSQL 준비

```bash
# Postgres 실행 후
createdb -U <USER> hifis_db
createdb -U <USER> hifis_test         # 테스트 전용
```

### 3) 환경변수 설정

`.env` 파일을 프로젝트 루트에 생성:

```env
HIFIS_DB_USER=hifis
HIFIS_DB_PASSWORD=<비밀번호>
HIFIS_DB_NAME=hifis_db
HIFIS_DB_HOST=localhost
HIFIS_DB_PORT=5432

JWT_SECRET_KEY=<랜덤 문자열>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=480

SOLAPI_API_KEY=<발급>
SOLAPI_API_SECRET=<발급>
SOLAPI_SENDER=<인증된 발신번호>

CLAUDE_API_KEY=<발급>

# 프론트 도메인 (콤마 구분), 비어있으면 CORS 미들웨어 미적용
CORS_ALLOWED_ORIGINS=http://localhost:5173
```

### 4) DB 마이그레이션

```bash
alembic upgrade head
```

### 5) SUPER_ADMIN 계정 생성

`alembic` 마이그레이션 후 직접 DB에 INSERT하거나, Python 셸로:

```python
from app.models.branch import Branch
from app.db.session import SessionLocal
from app.models.admin.admin import Admin
from app.core.security import hash_password

db = SessionLocal()
admin = Admin(
    email="admin@example.com",
    password_hash=hash_password("your-password"),
    name="대표",
    role="SUPER_ADMIN",
    branch_id=None,
)
db.add(admin); db.commit()
```

### 6) 서버 실행

```bash
uvicorn app.main:app --reload
```

기본 포트 `8000`. API 문서: <http://localhost:8000/docs>

---

## 테스트

```bash
pytest                              # 전체 (현재 72개)
pytest tests/integration            # 통합 테스트만
pytest -v                           # 각 테스트 이름까지
pytest -k "permission"              # 이름 매칭
pytest --cov=app                    # 커버리지
```

테스트는 별도 `hifis_test` DB에서 트랜잭션 rollback 방식으로 격리됩니다. Solapi/Claude는 자동 mock되어 실제 호출되지 않습니다.

---

## 폴더 구조 (요약)

```
app/
├── main.py                  # FastAPI 앱 + lifespan + CORS + /health
├── core/                    # config, security
├── db/                      # SQLAlchemy 기반 + 세션
├── utils/                   # validators, masking
├── api/                     # 라우터 (요청/응답만)
│   ├── deps.py              # 인증·권한 헬퍼
│   └── {registrations,passes,admin,messaging}/
├── models/                  # SQLAlchemy 모델
│   └── {registrations,passes,admin,messaging}/
├── schemas/                 # Pydantic 스키마
│   └── {registrations,passes,admin,messaging}/
└── services/                # 비즈니스 로직 (DB 접근)
    └── {registrations,passes,admin,messaging}/

tests/
├── conftest.py              # DB·TestClient·외부 API mock fixture
├── test_*.py                # 순수 로직 (DB X)
└── integration/             # DB 통합 (라우터까지)

alembic/                     # 마이그레이션
```

도메인 모델·API 명세·코드 규칙 등 자세한 설계는 [.claude/CLAUDE.md](./.claude/CLAUDE.md) 참조.

---

## 주요 엔드포인트

### Public (인증 불필요)
- `POST /reservations` 예약 신청
- `POST /members` 회원가입
- `POST /pt-applications` PT 신청
- `GET /{membership,pt,locker,clothes}-passes?branch_id=` 지점별 상품
- `GET /health` 헬스체크 (DB 포함)

### Admin (JWT 필요)
- `POST /admin/login` 로그인 → 토큰
- `/admin/{members,pt-applications,reservations,holds,messages,...}` CRUD
- `/admin/stats/{referral,motivation}?branch_id=` 통계

전체 명세는 서버 실행 후 `/docs` (Swagger UI) 에서 확인 가능.

---

## 알림톡

- **고정 템플릿** (11종 트리거) : `services/messaging/message_templates.py`
- **AI 생성** (홀딩 신청/취소만) : `services/messaging/claude.py` (claude-haiku-4-5)
- **발송** : `services/messaging/solapi.py` (실패 시 3회 재시도)
- **스케줄러** (매일 08:00 KST) : `services/messaging/scheduler.py`
  - 예약 +3/+5일 미등록 권유
  - 가입 +7/+14/+30일 D+N 알림
  - 만기 -5/-2일 / 당일 / +30일 안내
  - 만기 도래 자동 EXPIRED 처리

---

## 권한

- **SUPER_ADMIN** : 전 지점 접근
- **FC** (지점 담당자) : 본인 지점만 (타 지점 데이터 접근 시 404)

권한 분기 헬퍼 : `api/deps.py` (`resolve_branch_filter`, `assert_branch_access`)

---

## 개발 규칙 (요약)

- 비즈니스 로직은 `services/`에서만, 라우터는 요청/응답 처리만
- DB 접근 = `services/` 안에서만
- 모든 PK는 UUID, 모든 테이블에 `created_at`
- DB 타임존 Asia/Seoul 고정, Python의 "오늘" = `datetime.now(ZoneInfo("Asia/Seoul")).date()`
- 외부 API 호출은 try/except 필수
- 전화번호는 로그에 마스킹
- 주석은 한국어

자세한 규칙·트레이드오프는 [.claude/CLAUDE.md](./.claude/CLAUDE.md)에 정리되어 있음.

---

## 라이선스

Private. 무단 사용·복제 금지.
