import logging

from contextlib import asynccontextmanager
from app.services.scheduler import start_scheduler, stop_scheduler

from fastapi import FastAPI

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