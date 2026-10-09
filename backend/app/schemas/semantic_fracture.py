from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FractureClassification(StrEnum):
    NO_FRACTURE = "NO_FRACTURE"
    IDENTITY_DISAGREEMENT = "IDENTITY_DISAGREEMENT"
    VALIDITY_DISAGREEMENT = "VALIDITY_DISAGREEMENT"
    STRUCTURAL_DISAGREEMENT = "STRUCTURAL_DISAGREEMENT"
    BOUNDARY_DISAGREEMENT = "BOUNDARY_DISAGREEMENT"
    EMBEDDED_OBJECT_DISAGREEMENT = "EMBEDDED_OBJECT_DISAGREEMENT"
    CAPABILITY_DISAGREEMENT = "CAPABILITY_DISAGREEMENT"
    BEHAVIORAL_DISAGREEMENT = "BEHAVIORAL_DISAGREEMENT"


class FractureRecord(BaseModel):
    id: str
    classification: FractureClassification
    severity: Literal["MEDIUM", "HIGH"]
    source_signal: str
    interpreters: list[str]
    evidence: dict[str, Any]
    graph_node_ids: list[str]
    rationale: str


class ContextSignal(BaseModel):
    code: str
    source: Literal["FASTSCAN"] = "FASTSCAN"
    severity: Literal["INFO", "WARNING", "ERROR"]
    message: str


class FractureSummary(BaseModel):
    fracture_count: int
    highest_severity: Literal["MEDIUM", "HIGH"] | None


class SemanticFractureResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: UUID
    sha256: str
    fracture_detected: bool
    fractures: list[FractureRecord]
    context_signals: list[ContextSignal]
    summary: FractureSummary
    status: Literal["COMPLETE"] = "COMPLETE"
