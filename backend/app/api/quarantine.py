from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.api.sentinel import sentinel_service
from app.services.quarantine_runtime import quarantine_service
from app.schemas.quarantine import PublicQuarantineRecord, public_record
from app.services.quarantine_service import QuarantineError


router = APIRouter(prefix="/api/quarantine", tags=["quarantine"])


@router.get("", response_model=list[PublicQuarantineRecord])
def list_quarantine():
    return [public_record(item) for item in quarantine_service.list()]


@router.get("/{quarantine_id}", response_model=PublicQuarantineRecord)
def get_quarantine(quarantine_id: UUID):
    record = quarantine_service.get(quarantine_id)
    if record is None:
        raise HTTPException(404, "Quarantine record not found")
    return public_record(record)


@router.get("/artifact/{artifact_id}", response_model=PublicQuarantineRecord)
def get_artifact_quarantine(artifact_id: UUID):
    record = quarantine_service.for_artifact(artifact_id)
    if record is None:
        raise HTTPException(404, "Artifact has no quarantine record")
    return public_record(record)


@router.post("/{quarantine_id}/restore", response_model=PublicQuarantineRecord)
def restore_quarantine(quarantine_id: UUID):
    try:
        record = quarantine_service.restore(quarantine_id)
    except QuarantineError as exc:
        raise HTTPException(409, str(exc)) from exc
    sentinel_service._emit("QUARANTINE_RESTORED", "Authenticated artifact restored",
                           file_name=record.original_name, artifact_id=record.artifact_id,
                           quarantine_id=record.quarantine_id, containment_trigger=record.trigger,
                           verified_state=record.verified_state)
    return public_record(record)
