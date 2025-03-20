"""RAG Quality Monitor — FastAPI application.

Start with::

    uvicorn app.main:app --host 127.0.0.1 --port 8000

The offline deterministic mode works without any API key.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from . import __version__
from .api import ROUTERS
from .api.deps import check_api_key, check_rate_limit
from .config import settings
from .db import engine, init_db
from .scheduler import scheduler

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)
logger = logging.getLogger("rqm")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if settings.scheduler_enabled:
        scheduler.start()
        logger.info("scheduler started (tick=%ss)", scheduler.interval_s)
    logger.info("%s %s ready (environment=%s)", settings.app_name, __version__, settings.environment)
    try:
        yield
    finally:
        if settings.scheduler_enabled:
            scheduler.stop()
        engine.dispose()
        logger.info("shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "Evaluate, compare, gate and monitor RAG applications. The offline deterministic mode works with no API key."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    started = time.perf_counter()
    try:
        check_api_key(request)
        check_rate_limit(request)
    except Exception as exc:  # noqa: BLE001 - FastAPI HTTPException
        status = getattr(exc, "status_code", 401)
        return JSONResponse(status_code=status, content={"detail": str(getattr(exc, "detail", exc))})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Response-Time-ms"] = f"{(time.perf_counter() - started) * 1000:.1f}"
    return response


@app.get("/health", tags=["system"])
def health():
    """Liveness probe — never requires authentication."""
    return {"status": "ok", "service": "rag-quality-monitor", "version": __version__}


@app.get("/ready", tags=["system"])
def ready():
    """Readiness probe — verifies that the database answers."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"status": "unavailable", "detail": str(exc)[:200]})
    return {"status": "ready", "database": "ok", "scheduler": settings.scheduler_enabled}


@app.get("/", tags=["system"])
def root():
    return {
        "service": "rag-quality-monitor",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready",
        "offline_mode": "All deterministic metrics work without an API key.",
        "api_sections": sorted({r.prefix for r in ROUTERS}),
    }


for router in ROUTERS:
    app.include_router(router)
