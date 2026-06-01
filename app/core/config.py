from typing import Annotated
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode
from pydantic import field_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    HIFIS_DB_USER: str
    HIFIS_DB_PASSWORD: str
    HIFIS_DB_NAME: str
    HIFIS_DB_HOST: str
    HIFIS_DB_PORT: int

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480
    JWT_REFRESH_EXPIRE_DAYS: int = 30

    SOLAPI_API_KEY: str
    SOLAPI_API_SECRET: str
    SOLAPI_SENDER: str

    CLAUDE_API_KEY: str

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str
    SMTP_PASSWORD: str
    SMTP_FROM_NAME: str = "피트니스스타 HiFIS"

    APP_BASE_URL: str = "http://localhost:8000"

    # Web Push (VAPID) - python -m py_vapid 로 키페어 생성 후 .env에 저장
    # 비어있으면 push 발송 자체를 건너뜀 (DB 알림은 정상 저장)
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_CONTACT_EMAIL: str = ""

    # Sentry - 비어있으면 no-op (개발 환경에선 비워둠, 운영에서만 DSN 박기)
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "production"
    # 트래픽 샘플링 - 0.0~1.0. 작은 사장님 사업이라 0.0(에러만)으로 충분
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0

    # 알림톡(Solapi LMS) 발송 활성화 - 운영 전엔 false로 두고 회원 발송 차단.
    # false일 때 send_sms는 호출 즉시 (True, None) 반환 + 로그만 남김 (Solapi 호출 X).
    # 이력(Message 테이블)은 SUCCESS로 저장돼 화면에 발송된 것처럼 보이지만 실 발송 0.
    MESSAGING_ENABLED: bool = True

    # 브로제이(BroJ) 자동 회원 등록 - 화순점만 운영 중. 다른 지점 운영 시 별도 계정·토큰 필요.
    # 토글은 Branch.broj_enabled (지점별). 환경변수는 인증 정보 1세트만 보관.
    # JGROUP_TOKEN은 브로제이 브라우저 네트워크탭에서 복사 (만료 시 사장님이 갱신해서 .env 업데이트)
    BROJ_LOGIN_ID: str = ""
    BROJ_LOGIN_PW: str = ""
    BROJ_JGROUP_TOKEN: str = ""

    # 다짐(Dagym) 자동 회원 등록 - 동광주점 활성 (첨단점은 추후 GYM_ID 분기 시 활성).
    # GraphQL 기반. 비밀번호는 평문 → 코드가 SHA-256 hex로 변환해 전송.
    # 토큰은 로그인 응답에 포함, 메모리 캐싱 + 401/403 시 재로그인.
    DAJIM_LOGIN_EMAIL: str = ""
    DAJIM_LOGIN_PW: str = ""
    DAJIM_GYM_ID: str = ""

    CORS_ALLOWED_ORIGINS: Annotated[list[str], NoDecode] = []

    @field_validator("CORS_ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _parse_cors(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg2://{self.HIFIS_DB_USER}:{self.HIFIS_DB_PASSWORD}"
            f"@{self.HIFIS_DB_HOST}:{self.HIFIS_DB_PORT}/{self.HIFIS_DB_NAME}"
        )
    
settings = Settings()

