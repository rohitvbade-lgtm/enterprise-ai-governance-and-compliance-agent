"""
Async SQLAlchemy database session factory.

Usage:
    async with get_db() as db:
        result = await db.execute(...)
"""
from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from backend.app.config.settings import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_bound_loop: asyncio.AbstractEventLoop | None = None


def get_engine() -> AsyncEngine:
    global _engine, _session_factory, _bound_loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    # Reset engine if the current event loop changed (e.g. across pytest test functions)
    if _engine is not None and _bound_loop is not loop:
        _engine = None
        _session_factory = None

    if _engine is None:
        settings = get_settings()
        kwargs: dict[str, Any] = {
            "echo": settings.app_debug,
            "pool_pre_ping": True,
        }
        if "pytest" in sys.modules or settings.app_env in ["test", "testing"]:
            kwargs["poolclass"] = NullPool
        else:
            kwargs["pool_size"] = 10
            kwargs["max_overflow"] = 20

        _engine = create_async_engine(settings.database_url, **kwargs)
        _bound_loop = loop
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    engine = get_engine()
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Context manager that yields a database session and handles commit/rollback."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_dependency() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an AsyncSession."""
    async with get_db() as session:
        yield session


async def close_engine() -> None:
    """Dispose the engine on application shutdown."""
    global _engine, _session_factory, _bound_loop
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        _bound_loop = None
