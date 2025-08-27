Param([string]$Root = ".")

$backend = Join-Path $Root "backend"
$app = Join-Path $backend "app"

if (!(Test-Path $backend)) { Write-Error "backend/ not found. Run from repo root."; exit 1 }
if (!(Test-Path $app)) { New-Item -ItemType Directory $app | Out-Null }

# Move backend subfolders into backend/app/
$moveThese = @("adapters","agents","api","core","data","kb","models","scripts","services","tests")
foreach($d in $moveThese){
  $src = Join-Path $backend $d
  if (Test-Path $src) { Move-Item $src -Destination $app -Force }
}

# Ensure __init__.py files (makes them real packages)
$pkgDirs = @("","api","api/routers","agents","adapters","core","models","services")
foreach($d in $pkgDirs){
  $p = Join-Path $app $d
  if (!(Test-Path $p)) { New-Item -ItemType Directory $p | Out-Null }
  $init = Join-Path $p "__init__.py"
  if (!(Test-Path $init)) { Set-Content $init "" }
}

# Overwrite app/api/main.py with correct absolute imports
Set-Content (Join-Path $app "api\main.py") @"
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.logging import setup_logging
from app.core.config import get_settings
from app.api.routers import incidents

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
    app.include_router(incidents.router)
    logger.info("App started in {} mode", settings.app_env)
    return app

app = create_app()
"@

# Overwrite app/api/routers/incidents.py (uses app.* imports)
Set-Content (Join-Path $app "api\routers\incidents.py") @"
from fastapi import APIRouter, HTTPException
from typing import List
from app.models.incident import Incident
from app.services.pipeline import INCIDENTS, PIPELINE
from app.agents.base import AgentContext

router = APIRouter(prefix="/incidents", tags=["incidents"])

@router.get("/", response_model=List[Incident])
def list_incidents():
    return list(INCIDENTS.values())

@router.get("/{incident_id}", response_model=Incident)
def get_incident(incident_id: str):
    inc = INCIDENTS.get(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc

@router.post("/detect", response_model=Incident)
def detect_incident(incident: Incident):
    ctx = AgentContext(incident=incident, settings=PIPELINE.settings)
    PIPELINE.detector.run(ctx)
    INCIDENTS[incident.id] = incident
    return incident

@router.post("/{incident_id}/run")
def run_pipeline(incident_id: str):
    inc = INCIDENTS.get(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    out = PIPELINE.run_all(inc)
    return out
"@

Write-Host "`n✅ Converted to package layout: backend/app/*"
