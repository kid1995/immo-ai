"""FastAPI entry point with lifespan, CORS, and router registration."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.database import engine
from core.logging import setup_logging, get_logger
from core.redis import close_redis

from apps.api.routers import listings, analysis, agent

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown events."""
    setup_logging()
    log.info("starting", env=settings.env)
    yield
    # Shutdown
    await engine.dispose()
    await close_redis()
    log.info("shutdown_complete")


app = FastAPI(
    title="immo-ai",
    description="AI-powered commercial real estate finder for Vietnamese business owners in Germany",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"] if not settings.is_production else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(listings.router, prefix="/api/listings", tags=["listings"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "env": settings.env}
