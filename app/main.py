from fastapi import FastAPI

from app.db.base import Base
from app.db.session import engine

# 테이블 생성을 위해 모델 import 필요
from app.models import branch as _branch_model

from app.api import branch as branch_api

app = FastAPI(title="HiFIS Server")

Base.metadata.create_all(bind=engine)

app.include_router(branch_api.public_router)
app.include_router(branch_api.admin_router)

@app.get("/")
def read_root():
    return {"message": "Hello HiFIS!!"}