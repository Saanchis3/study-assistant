from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models
from app.db import Base, engine
from app.routers import cards, documents


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Study Assistant", lifespan=lifespan)

app.include_router(documents.router)
app.include_router(cards.router)


@app.get("/health")
def health():
    return {"status": "ok"}