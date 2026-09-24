from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.router import api_router
from core.config import settings
from database.base import Base
from database.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)

    yield


app = FastAPI(title="AI Chat API", version="2.0.0", lifespan=lifespan)

ALLOWED_ORIGINS = list(dict.fromkeys([
    settings.FRONTEND_ORIGIN,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]))

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
    allow_origins=ALLOWED_ORIGINS,
)

app.include_router(api_router, prefix="/api")


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
