import logging

from contextlib import asynccontextmanager
from app.services.messaging.scheduler import start_scheduler, stop_scheduler

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException
from app.db.deps import get_db

from app.core.config import settings
from app.core.rate_limit import limiter
from app.api import branch as branch_api
from app.api.registrations import reservation as reservation_api
from app.api.passes import membership as membership_pass_api
from app.api.passes import pt as pt_pass_api
from app.api.registrations import member as member_api
from app.api import enums as enums_api
from app.api.registrations import pt_application as pt_application_api
from app.api.admin import admin as admin_api
from app.api.messaging import message as message_api
from app.api.admin import stats as stats_api
from app.api import hold as hold_api
from app.api.passes import locker as locker_pass_api
from app.api.passes import clothes as clothes_pass_api

# 앱 전역 logging 설정 (root logger에 핸들러 부착)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# httpx는 외부 API 호출(Solapi·Claude)마다 INFO 로그를 찍어 소음이 큼 → WARNING으로
logging.getLogger("httpx").setLevel(logging.WARNING)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작 시 스케줄러 켜고, 종료 시 끄기"""
    start_scheduler()
    yield
    stop_scheduler()

app = FastAPI(title="HiFIS Server", lifespan=lifespan)

# rate limiting (slowapi) - limiter 등록 + 429(Too Many Requests) 응답 핸들러
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

if settings.CORS_ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=3600,
    )

app.include_router(branch_api.public_router)
app.include_router(branch_api.admin_router)
app.include_router(reservation_api.public_router)
app.include_router(reservation_api.admin_router)
app.include_router(membership_pass_api.public_router)
app.include_router(membership_pass_api.admin_router)
app.include_router(pt_pass_api.public_router)
app.include_router(pt_pass_api.admin_router)
app.include_router(member_api.public_router)
app.include_router(member_api.admin_router)
app.include_router(enums_api.public_router)
app.include_router(pt_application_api.public_router)
app.include_router(pt_application_api.admin_router)
app.include_router(admin_api.public_router)
app.include_router(admin_api.admin_router)
app.include_router(admin_api.me_router)
app.include_router(message_api.router) 
app.include_router(message_api.admin_router) 
app.include_router(stats_api.admin_router)
app.include_router(hold_api.admin_router)
app.include_router(locker_pass_api.public_router)
app.include_router(locker_pass_api.admin_router)
app.include_router(clothes_pass_api.public_router)
app.include_router(clothes_pass_api.admin_router)

@app.get("/")
def read_root():
    return {"message": "Hello HiFIS!!"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "ok"}
    except Exception:
        raise HTTPException(503, "DB unavailable")
