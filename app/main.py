from fastapi import FastAPI

from app.api import branch as branch_api

app = FastAPI(title="HiFIS Server")


app.include_router(branch_api.public_router)
app.include_router(branch_api.admin_router)

@app.get("/")
def read_root():
    return {"message": "Hello HiFIS!!"}