from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QuarantineRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    quarantine_id: UUID
    artifact_id: UUID
    original_path: str
    container_path: str
    original_name: str
    sha256: str
    trigger: Literal["LAYA_SUSPICIOUS", "DETERMINISTIC_SUSPICIOUS"]
    laya_prediction: str | None = None
    laya_confidence: float | None = None
    verified_state: Literal["SUSPICIOUS", "FRACTURED"] | None = None
    reason_codes: list[str] = Field(default_factory=list)
    quarantined_at: datetime
    status: Literal["QUARANTINED", "RESTORED"] = "QUARANTINED"
    restored_at: datetime | None = None


class PublicQuarantineRecord(BaseModel):
    quarantine_id: UUID
    artifact_id: UUID
    original_name: str
    container_name: str
    sha256: str
    trigger: str
    laya_prediction: str | None
    laya_confidence: float | None
    verified_state: str | None
    reason_codes: list[str]
    quarantined_at: datetime
    status: str
    restored_at: datetime | None


def public_record(record: QuarantineRecord) -> PublicQuarantineRecord:
    return PublicQuarantineRecord(
        quarantine_id=record.quarantine_id, artifact_id=record.artifact_id,
        original_name=record.original_name, container_name=__import__("pathlib").Path(record.container_path).name,
        sha256=record.sha256, trigger=record.trigger,
        laya_prediction=record.laya_prediction, laya_confidence=record.laya_confidence,
        verified_state=record.verified_state, reason_codes=record.reason_codes,
        quarantined_at=record.quarantined_at, status=record.status, restored_at=record.restored_at,
    )
