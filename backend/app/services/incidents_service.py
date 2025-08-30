from sqlalchemy.ext.asyncio import AsyncSession
from ..repositories.incidents import IncidentRepository
from ..schemas.incident import IncidentCreate, IncidentUpdate, IncidentEventCreate
from ..models import Incident, IncidentEvent

repo = IncidentRepository()

async def create_incident(db: AsyncSession, data: IncidentCreate) -> Incident:
    obj = await repo.create(db, data)
    return obj

async def list_incidents(db: AsyncSession, limit=50, offset=0):
    return await repo.list(db, limit, offset)

async def get_incident(db: AsyncSession, incident_id: str):
    return await repo.get(db, incident_id)

async def update_incident(db: AsyncSession, incident_id: str, data: IncidentUpdate):
    return await repo.update(db, incident_id, data)

async def delete_incident(db: AsyncSession, incident_id: str):
    return await repo.delete(db, incident_id)

async def add_event(db: AsyncSession, incident_id: str, ev: IncidentEventCreate) -> IncidentEvent | None:
    return await repo.add_event(db, incident_id, ev)
