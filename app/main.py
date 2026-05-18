import logging

from contextlib import asynccontextmanager
from app.services.scheduler import start_scheduler, stop_scheduler

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException
from app.db.deps import get_db

from app.core.config import settings
from app.api import branch as branch_api
from app.api import reservation as reservation_api
from app.api import membership_pass as membership_pass_api
from app.api import pt_pass as pt_pass_api
from app.api import member as member_api
from app.api import enums as enums_api
from app.api import pt_application as pt_application_api
from app.api import admin as admin_api
from app.api import message as message_api
from app.api import stats as stats_api
from app.api import hold as hold_api
from app.api import locker_pass as locker_pass_api
from app.api import clothes_pass as clothes_pass_api

# 앱 전역 logging 설정 (root logger에 핸들러 부착)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작 시 스케줄러 켜고, 종료 시 끄기"""
    start_scheduler()
    yield
    stop_scheduler()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(title="HiFIS Server", lifespan=lifespan)

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
