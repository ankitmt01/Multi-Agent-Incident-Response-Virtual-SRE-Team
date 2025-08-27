from fastapi import APIRouter
from app.models.incident import RemediationCandidate

router = APIRouter(prefix="/debug", tags=["debug"])

@router.post("/validate-remediation", response_model=RemediationCandidate)
def validate_remediation(rc: RemediationCandidate):
    return rc
