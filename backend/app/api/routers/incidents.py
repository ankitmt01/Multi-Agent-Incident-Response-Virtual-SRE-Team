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
