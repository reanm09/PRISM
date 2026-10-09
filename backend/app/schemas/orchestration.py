from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.laya_triage import LayaTriageResult


class PrismOrchestrationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: UUID
    triage: LayaTriageResult

    routing_decision: Literal["PASS", "DEEP_SCAN", "PRISM_LAB"]
    deep_scan_performed: bool

    verified_state: Literal["SUSPICIOUS", "FRACTURED"] | None = None
    ambiguity_observed: bool = False

    suspicious_verified: bool | None = None
    fracture_detected: bool | None = None

    reason_codes: list[str]
