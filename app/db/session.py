from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

@event.listens_for(engine, "connect")
def _set_kst_timezone(dbapi_connection, connection_record):
    """DB 세션 타임존을 KST로 고정 - CURRENT_DATE / func.date() 등이 KST 기준,
    timestamptz 응답도 +09:00로 직렬화. 저장값은 UTC 그대로(변환 없음)."""
    with dbapi_connection.cursor() as cursor:
        cursor.execute("SET TIME ZONE 'Asia/Seoul'")

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)