from pydantic_settings import BaseSettings, SettingsConfigDict

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

    SOLAPI_API_KEY: str
    SOLAPI_API_SECRET: str
    SOLAPI_SENDER: str

    CLAUDE_API_KEY: str

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg2://{self.HIFIS_DB_USER}:{self.HIFIS_DB_PASSWORD}"
            f"@{self.HIFIS_DB_HOST}:{self.HIFIS_DB_PORT}/{self.HIFIS_DB_NAME}"
        )
    
settings = Settings()

