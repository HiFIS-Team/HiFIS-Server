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

