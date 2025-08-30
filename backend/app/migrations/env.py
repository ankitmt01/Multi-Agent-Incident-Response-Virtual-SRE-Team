# backend/app/migrations/env.py
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy import create_engine  # sync engine for offline
from sqlalchemy.ext.asyncio import create_async_engine  # async engine for online
from app import models


# Import your metadata
from app.core.db import Base  # Base.metadata should contain all ORM tables
from app.core.db import Base
target_metadata = Base.metadata


# Alembic Config object, which provides access to values within alembic.ini
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    # Prefer ALEMBIC_DATABASE_URL, fall back to Postgres in docker-compose
    return os.getenv("ALEMBIC_DATABASE_URL", "postgresql+psycopg://air:air@db:5432/air")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode' with async engine."""
    connectable = create_async_engine(get_url(), poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


# Alembic 1.14 supports async; choose online/offline based on context
if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio
    asyncio.run(run_migrations_online())
