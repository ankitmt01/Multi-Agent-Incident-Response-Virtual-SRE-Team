from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.logging import setup_logging
from app.core.config import get_settings
from app.api.routers import incidents, debug  # ← import both here

logger = setup_logging()
settings = get_settings()

def create_app() -> FastAPI:
    app = FastAPI(title="Agentic Incident Response API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(incidents.router)
    app.include_router(debug.router)   # ← add this line

    logger.info("App started in {} mode", settings.app_env)
    return app

app = create_app()
