# app/api/main.py
from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging import setup_logging
from app.core.config import get_settings
from app.core.db import engine, Base
from sqlalchemy.exc import OperationalError

logger = setup_logging()
settings = get_settings()

def create_app() -> FastAPI:
    app = FastAPI(title="Agentic Incident Response API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # incidents router (singular or plural)
    incidents_module = None
    try:
        from app.api.routers import incidents as _inc
        incidents_module = _inc
    except Exception:
        from app.api.routers import incident as _inc  # fallback
        incidents_module = _inc
    app.include_router(incidents_module.router)

    # optional routers
    for modname in ("kb", "demo", "debug"):
        try:
            mod = __import__(f"app.api.routers.{modname}", fromlist=["router"])
            if hasattr(mod, "router"):
                app.include_router(mod.router)
        except Exception:
            pass

    @app.on_event("startup")
    async def _ensure_schema():
        try:
            # ⬇️ this import registers all ORM tables on Base.metadata
            import app.models.sql  # noqa: F401
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("DB schema ensured (create_all).")
        except OperationalError as e:
            logger.error("DB not reachable at startup: %s", e)
            # let container restart; that’s fine for dev

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "env": settings.app_env}

    logger.info("App started in %s mode", settings.app_env)
    return app

app = create_app()
