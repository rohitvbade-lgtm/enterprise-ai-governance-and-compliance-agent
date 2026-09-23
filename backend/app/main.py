"""
FastAPI application entry point.

Run with: uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config.settings import get_settings
from backend.app.db.session import get_engine, close_engine


def _configure_logging(debug: bool = False) -> None:
    """Configure structlog for structured JSON logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            10 if debug else 20  # DEBUG if debug else INFO
        ),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# Configure logging eagerly at import time so that module-level loggers in
# imported submodules work before the async lifespan runs.
_configure_logging(debug=False)

logger = structlog.get_logger(__name__)


def _configure_langsmith(settings: Any) -> None:
    """Enable LangSmith tracing if configured. App runs fine without it."""
    if settings.langsmith_enabled:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
        logger.info("langsmith_tracing_enabled", project=settings.langsmith_project)
    else:
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
        logger.info("langsmith_tracing_disabled")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown."""
    settings = get_settings()
    # Re-configure with the actual debug flag from settings
    _configure_logging(debug=settings.app_debug)
    _configure_langsmith(settings)

    logger.info(
        "application_starting",
        name=settings.app_name,
        version=settings.app_version,
        env=settings.app_env,
        llm_provider=settings.llm_provider,
    )

    # Verify database connection on startup
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        logger.info("database_connection_ok")
    except Exception as e:
        logger.error("database_connection_failed", error=str(e))
        # Don't crash on startup — let individual requests fail gracefully

    yield  # Application is running

    logger.info("application_shutting_down")
    await close_engine()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Enterprise AI Governance & Compliance Platform",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS — restrict in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_development else ["https://your-dashboard.example.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routes ────────────────────────────────────────────────────────────────
    from backend.app.api.v1 import router as v1_router
    app.include_router(v1_router, prefix="/api/v1")

    # ── Health endpoint ───────────────────────────────────────────────────────
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict[str, Any]:
        """
        Health check endpoint.

        Verifies database connectivity and returns system status.
        Does NOT require authentication — safe for load balancer probes.
        """
        db_ok = False
        try:
            from sqlalchemy import text as sa_text
            engine = get_engine()
            async with engine.connect() as conn:
                await conn.execute(sa_text("SELECT 1"))
            db_ok = True
        except Exception as e:
            logger.warning("health_check_db_failed", error=str(e))

        status = "healthy" if db_ok else "degraded"
        return {
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": settings.app_version,
            "environment": settings.app_env,
            "database": "connected" if db_ok else "unavailable",
            "llm_provider": settings.llm_provider,
            "langsmith_enabled": settings.langsmith_enabled,
        }

    return app


app = create_app()

