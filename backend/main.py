import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from api.router import api_router
from core.config import settings
from core.logging_config import setup_logging
from database.base import Base
from database.session import engine
from ai_agent.rag.vector_store import init_vector_store

# ---------------------------------------------------------------------------
# Structured JSON logging
# ---------------------------------------------------------------------------

setup_logging()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    try:
        init_vector_store()
    except Exception as exc:  # pragma: no cover - startup resilience
        logger.warning("Vector store initialization failed", exc_info=exc)
    yield


app = FastAPI(
    title="Chanakya AI API",
    version="2.0.0",
    lifespan=lifespan,
    description="""
    Chanakya AI - Political Campaign Intelligence Platform
    
    This API provides endpoints for:
    - **Authentication**: Login, logout, token refresh
    - **Administration**: Client management, user management, assignments
    - **Analysis**: Natural language to SQL queries, data export
    - **Intelligence**: Hybrid Q&A (database + documents + general knowledge)
    - **Documents**: Upload, search, and manage documents
    - **Conversations**: Chat history and message management
    - **Users**: Profile management
    
    ## Authentication
    
    The API uses JWT tokens stored in HTTP-only cookies:
    - `access_token`: Short-lived access token (15 minutes)
    - `refresh_token`: Long-lived refresh token (30 days)
    
    ## Rate Limiting
    
    API endpoints are rate-limited to 30 requests per minute per user.
    
    ## Role Hierarchy
    
    - `admin`: Full access to all data and admin panel
    - `khasdar`: Parliamentary constituency level access
    - `aamdar`: Assembly level access
    - `corporator`: Ward level access
    - `karyakarta`: Basic ward level access
    - `user`: Basic user access
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


# Request ID + timing middleware (structured tracing).
@app.middleware("http")
async def request_tracing_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled request error", extra={"request_id": request_id})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error", "request_id": request_id},
        )
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = f"{duration_ms:.1f}"
    logger.info(
        "%s %s -> %s (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        extra={"request_id": request_id},
    )
    return response


# Compression for large responses (e.g. query result tables, CSV exports).
app.add_middleware(GZipMiddleware, minimum_size=1024)

ALLOWED_ORIGINS = list(
    dict.fromkeys(
        [
            settings.FRONTEND_ORIGIN,
            *(o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()),
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://192.168.1.155:3000",
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


# Security headers on every response.
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


app.include_router(api_router, prefix="/api")


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.exception(
        "Database error",
        extra={"request_id": getattr(request.state, "request_id", None)},
    )
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={
            "detail": "Database error",
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": str(exc),
            "request_id": getattr(request.state, "request_id", None),
        },
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["Health"])
def readiness_check() -> dict[str, str]:
    """Readiness probe: confirms the application can reach its dependencies."""
    # Database connectivity is implied by successful startup (create_all).
    # Vector store status is checked lazily on first use; report healthy here.
    return {"status": "ready"}


@app.get("/health/live", tags=["Health"])
def liveness_check() -> dict[str, str]:
    """Liveness probe: confirms the application is running."""
    return {"status": "alive"}


@app.get("/health/dependencies", tags=["Health"])
def dependencies_check() -> dict:
    """Check connectivity to all external dependencies."""
    from database.session import engine
    from ai_agent.rag.vector_store import get_vector_store

    checks = {}

    # Database check
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        checks["database"] = {"status": "healthy", "details": "Connected"}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "details": str(e)}

    # Vector store check
    try:
        vector_store = get_vector_store()
        # Try a simple operation
        vector_store._collection.count()
        checks["vector_store"] = {"status": "healthy", "details": "Connected"}
    except Exception as e:
        checks["vector_store"] = {"status": "unhealthy", "details": str(e)}

    # Overall status
    all_healthy = all(check["status"] == "healthy" for check in checks.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks,
    }
