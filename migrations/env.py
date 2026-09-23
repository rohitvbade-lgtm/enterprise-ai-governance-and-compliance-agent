"""
Alembic environment configuration.

Loads DATABASE_URL from settings so credentials are never in alembic.ini.
Supports async SQLAlchemy (asyncpg driver).
"""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Load all models so Alembic can detect them in metadata
from backend.app.models import Base  # noqa: F401 — triggers all model imports
from backend.app.config.settings import get_settings

# Alembic Config object — provides access to .ini values
config = context.config

# Configure Python logging from the ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the SQLAlchemy metadata for autogenerate support
target_metadata = Base.metadata

# Inject DATABASE_URL from settings (overrides the empty value in alembic.ini)
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection required)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations against the live async database."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

