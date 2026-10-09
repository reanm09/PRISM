from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.fastscan import (
    PDFSecurityPrecursors, PDFStructuralFeatures, PNGStructuralFeatures,
    ZIPSecurityPrecursors, ZIPStructuralFeatures,
)
from app.schemas.fracture_dataset import GroundTruthProvenance, SuspiciousEvidence
from app.schemas.semantic_fracture import FractureClassification


class TrainingEligibility(BaseModel):
    eligible: bool
    reasons: list[str]


FEATURE_STAGE = "FASTSCAN_PRE_TRIAGE"
FEATURE_CONTRACT_VERSION = "4.0"


class LayaModelInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claimed_extension: str
    observed_identity: str
    mime: str
    size_bytes: int
    entropy: float
    extension_consistent: bool | None
    fastscan_signals: list[str]
    structural_features: PDFStructuralFeatures | ZIPStructuralFeatures | PNGStructuralFeatures
    pretriage_security_features: PDFSecurityPrecursors | ZIPSecurityPrecursors | None

    @model_validator(mode="after")
    def family_appropriate_precursors(self):
        if self.structural_features.family != self.observed_identity:
            raise ValueError("Structural features do not match byte-observed family")
        precursor = self.pretriage_security_features
        if self.observed_identity in ("PDF", "ZIP"):
            if precursor is None or precursor.family != self.observed_identity:
                raise ValueError("Applicable security precursors are unavailable")
        elif self.observed_identity == "PNG" and precursor is not None:
            raise ValueError("PNG has no v4 security precursor contract")
        return self


class LayaTargets(BaseModel):
    artifact_state: Literal["BENIGN", "AMBIGUOUS", "SUSPICIOUS", "FRACTURED"]
    escalation: Literal["PASS", "DEEP_SCAN", "PRISM_LAB", "QUARANTINE"]
    fracture_target: Literal[0, 1]
    priority: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class LabelProvenance(BaseModel):
    source: Literal["VERIFIED_PRISM_EVIDENCE"] = "VERIFIED_PRISM_EVIDENCE"
    rules: list[str]
    ground_truth_evidence: "GroundTruthEvidence"
    controlled_source: GroundTruthProvenance | None = None
    suspicious_evidence: SuspiciousEvidence | None = Field(default=None, exclude_if=lambda value: value is None)


class GroundTruthEvidence(BaseModel):
    fracture_detected: bool
    fracture_types: list[FractureClassification]
    fracture_severity: Literal["MEDIUM", "HIGH"] | None


class LayaTrainingRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    record_id: str
    source_record_id: str
    artifact_id: UUID
    sha256: str
    split_group_id: str
    source_family: Literal["PDF", "ZIP", "PNG"]
    feature_stage: Literal["FASTSCAN_PRE_TRIAGE"] = FEATURE_STAGE
    feature_contract_version: Literal["4.0"] = FEATURE_CONTRACT_VERSION
    model_input: LayaModelInput
    targets: LayaTargets
    label_provenance: LabelProvenance


class LayaTrainingCandidate(BaseModel):
    source_record_id: str
    eligibility: TrainingEligibility
    record: LayaTrainingRecord | None


class LayaTriageResult(BaseModel):
    """Pre-triage model prediction.

    This is a routing prediction from FASTSCAN_PRE_TRIAGE evidence.
    It is not verified Semantic Fracture or suspicious ground truth.
    """

    model_config = ConfigDict(frozen=True)

    artifact_id: UUID
    sha256: str

    feature_stage: Literal["FASTSCAN_PRE_TRIAGE"] = FEATURE_STAGE
    feature_contract_version: Literal["4.0"] = FEATURE_CONTRACT_VERSION

    predicted_state: Literal[
        "BENIGN",
        "AMBIGUOUS",
        "SUSPICIOUS",
        "FRACTURED",
    ]

    answer_confidence: float = Field(ge=0.0, le=1.0)
    probabilities: dict[str, float]

    recommended_route: Literal[
        "PASS",
        "DEEP_SCAN",
        "PRISM_LAB",
    ]

    model_sha256: str
    model_input: LayaModelInput

