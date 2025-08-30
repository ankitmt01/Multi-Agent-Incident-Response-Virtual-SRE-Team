# app/api/main.py
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging import setup_logging
from app.core.config import get_settings

logger = setup_logging()
settings = get_settings()

def create_app() -> FastAPI:
    app = FastAPI(title="Agentic Incident Response API", version="0.1.0")

    # CORS (dev-friendly; tighten in prod)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "*"  # dev only
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Incidents router (handle singular OR plural filename) ---
    incidents_module = None
    try:
        from app.api.routers import incidents as _inc  # plural
        incidents_module = _inc
    except Exception:
        try:
            from app.api.routers import incident as _inc  # singular
            incidents_module = _inc
        except Exception as e:
            # Fail loudly with a clear message
            raise RuntimeError(
                "No incidents router found. Create app/api/routers/incident.py "
                "or incidents.py with `router = APIRouter(...)`."
            ) from e

    app.include_router(incidents_module.router)

    # --- Optional routers; ignore if missing/broken ---
    for modname in ("kb", "demo", "debug"):
        try:
            mod = __import__(f"app.api.routers.{modname}", fromlist=["router"])
            if hasattr(mod, "router"):
                app.include_router(mod.router)
        except Exception:
            pass

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    logger.info(f"App started in {settings.app_env} mode")
    return app

app = create_app()
