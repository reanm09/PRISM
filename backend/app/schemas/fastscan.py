from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ObservedIdentity(BaseModel):
    detected_type: str
    detected_mime: str
    magic_description: str


class ExtensionConsistency(BaseModel):
    extension_matches_observed: bool | None


class Statistics(BaseModel):
    entropy: float


class HeaderEvidence(BaseModel):
    first_bytes_hex: str


class IntegrityEvidence(BaseModel):
    sha256_matches_ingestion: bool


class FastScanSignal(BaseModel):
    code: str
    severity: Literal["INFO", "WARNING", "ERROR"]
    message: str


class FastScanResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: UUID
    sha256: str
    size_bytes: int
    claimed_extension: str
    observed: ObservedIdentity
    consistency: ExtensionConsistency
    statistics: Statistics
    header: HeaderEvidence
    integrity: IntegrityEvidence
    signals: list[FastScanSignal]
    scan_status: Literal["COMPLETE"] = "COMPLETE"
