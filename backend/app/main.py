from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.api.routers import incident, debug, demo  # keep your current filenames

settings = get_settings()

app = FastAPI(
    title=getattr(settings, "APP_NAME", "Agentic Incident API"),
    version=getattr(settings, "VERSION", "0.1.0"),
)

# CORS (UI dev at :5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(incident.router)
app.include_router(debug.router)
app.include_router(demo.router)

# Health / root
@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/")
def root():
    # handy when opening http://localhost:8000/
    return RedirectResponse(url="/docs")
