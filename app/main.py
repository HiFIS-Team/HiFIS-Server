from fastapi import FastAPI
from app.db.session import engine
from app.db.base import Base

app = FastAPI()

Base.metadata.create_all(bind=engine)

@app.get("/")
def read_root():
    return {"message": "Hello HiFIS!!"}