from __future__ import annotations
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from app.core.logging import setup_logging
from app.core.config import get_settings

logger = setup_logging()
settings = get_settings()

def create_app() -> FastAPI:
    app = FastAPI(title="Agentic Incident Response API", version="0.1.0")

    # avoid 307 redirects breaking the UI fetches
    app.router.redirect_slashes = False

    # CORS (dev)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Serve generated metrics CSVs (demo)
    metrics_dir = "/app/data/metrics"
    os.makedirs(metrics_dir, exist_ok=True)
    app.mount("/metrics", StaticFiles(directory=metrics_dir), name="metrics")

    # Incidents router (plural → singular fallback)
    try:
        from app.api.routers import incidents as _inc
        app.include_router(_inc.router)
    except Exception:
        try:
            from app.api.routers import incident as _inc
            app.include_router(_inc.router)
        except Exception as e:
            raise RuntimeError(
                "No incidents router found. Create app/api/routers/incident.py "
                "or incidents.py with `router = APIRouter(...)`."
            ) from e

    # Optional routers; ignore if missing
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

    logger.info("App started in %s mode", settings.app_env)
    return app

app = create_app()
