# app/core/db.py
from __future__ import annotations
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData

from .config import get_settings

# ---- SQLAlchemy base/metadata ----
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=convention)

class Base(DeclarativeBase):
    metadata = metadata

# ---- Engine / Session (single source of truth) ----
_settings = get_settings()

# Prefer snake_case; fall back to UPPERCASE for back-compat if present
_db_url = getattr(_settings, "database_url", None) or getattr(_settings, "DATABASE_URL", None)
if not _db_url:
    raise RuntimeError(
        "Database URL not configured. Set 'database_url' (or 'DATABASE_URL') in your environment/.env."
    )

engine = create_async_engine(_db_url, future=True, echo=False)
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
