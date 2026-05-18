# Python 3.14 slim 베이스
FROM python:3.14-slim

# curl: healthcheck 용
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성 먼저 복사 -> 캐시 최적화
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사 (테스트, 문서 등은 .dockerignore로 제외)
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# 비-root 유저로 실행 (보안)
RUN useradd -m -u 1000 appuser
USER appuser

EXPOSE 8000

# 컨테이너 자체 헬스체크
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

    CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
