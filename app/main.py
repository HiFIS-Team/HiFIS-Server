import logging

from fastapi import FastAPI

from app.api import branch as branch_api
from app.api import reservation as reservation_api
from app.api import membership_pass as membership_pass_api
from app.api import pt_pass as pt_pass_api
from app.api import member as member_api
from app.api import enums as enums_api
from app.api import pt_application as pt_application_api

# 앱 전역 logging 설정 (root logger에 핸들러 부착)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(title="HiFIS Server")

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

@app.get("/")
def read_root():
    return {"message": "Hello HiFIS!!"}