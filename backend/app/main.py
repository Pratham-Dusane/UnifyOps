"""
UnifyOps - FastAPI Application Entry Point

Mounts all 8 service routers behind a unified API gateway.
Applies middleware for request-ID propagation, CORS, and structured logging.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.middleware import RequestIDMiddleware, LoggingMiddleware
from app.routers import (
    health,
    auth,
    ingestion,
    graph,
    copilot,
    maintenance,
    compliance,
    lessons,
    notifications,
    admin,
    interviews,
    voice,
    agents,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle."""
    setup_logging()
    logger = get_logger("unifyops-gateway")
    logger.info(
        "application_starting",
        version=settings.app_version,
        environment=settings.app_env,
    )
    yield
    logger.info("application_shutting_down")


app = FastAPI(
    title="UnifyOps API",
    description=(
        "AI Industrial Knowledge Intelligence Platform. "
        "Unified Asset & Operations Brain for industrial plants."
    ),
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# --- Middleware (order matters: outermost first) ---
app.add_middleware(LoggingMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# --- Routers ---
# Gateway health
app.include_router(health.router)

# Auth & organisation management
app.include_router(auth.router)

# Eight PRD microservice skeletons (Section 7.1)
app.include_router(ingestion.router)
app.include_router(graph.router)
app.include_router(copilot.router)
app.include_router(maintenance.router)
app.include_router(compliance.router)
app.include_router(lessons.router)
app.include_router(notifications.router)
app.include_router(admin.router)
app.include_router(interviews.router)
app.include_router(voice.router)
app.include_router(agents.router)
