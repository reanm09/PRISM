from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PrismLabExperimentKind(StrEnum):
    FORCE_DEEP_INTERPRETATION = "FORCE_DEEP_INTERPRETATION"
    VERIFY_PDF_ACTIONS = "VERIFY_PDF_ACTIONS"
    VERIFY_ZIP_ENTRY_PATHS = "VERIFY_ZIP_ENTRY_PATHS"


EXPERIMENT_FAMILIES = {
    PrismLabExperimentKind.FORCE_DEEP_INTERPRETATION: frozenset({"PDF", "ZIP", "PNG"}),
    PrismLabExperimentKind.VERIFY_PDF_ACTIONS: frozenset({"PDF"}),
    PrismLabExperimentKind.VERIFY_ZIP_ENTRY_PATHS: frozenset({"ZIP"}),
}


class PrismLabExperimentRequest(BaseModel):
    """A typed, non-executable request for an allowlisted Lab experiment."""

    model_config = ConfigDict(extra="forbid")

    experiment_kind: PrismLabExperimentKind
    hypothesis: str | None = None
    rationale: str | None = None


class PrismLabExperimentResult(BaseModel):
    """Observed result of a controlled PRISM Lab experiment."""

    model_config = ConfigDict(frozen=True)

    experiment_id: UUID
    artifact_id: UUID
    experiment_kind: PrismLabExperimentKind

    status: Literal["COMPLETED"]
    deterministic: Literal[True] = True
    deep_scan_performed: bool

    hypothesis: str | None = None
    rationale: str | None = None

    verified_state: Literal["SUSPICIOUS", "FRACTURED"] | None = None
    ambiguity_observed: bool
    suspicious_verified: bool
    fracture_detected: bool

    reason_codes: list[str]
    observations: dict[str, str | int | bool | None] = Field(default_factory=dict)
