from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.router import api_router
from core.config import settings
from database.base import Base
from database.session import engine
from rag.vector_store import init_vector_store

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    init_vector_store()
    yield


app = FastAPI(title="AI Chat API", version="2.0.0", lifespan=lifespan)

ALLOWED_ORIGINS = list(
    dict.fromkeys(
        [
            settings.FRONTEND_ORIGIN,
            *(o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()),
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
)

# Private-network fallback so LAN clients (e.g. http://192.168.1.20:3000)
# pass preflight even when their exact IP isn't listed above.
LAN_ORIGIN_REGEX = (
    r"https?://(localhost|127\.0\.0\.1"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(:\d+)?"
)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=LAN_ORIGIN_REGEX,
)

app.include_router(api_router, prefix="/api")


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
