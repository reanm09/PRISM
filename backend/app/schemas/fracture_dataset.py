from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.fastscan import FastScanSignal
from app.schemas.interpretation import DisagreementSignal, InterpretationComparison, InterpreterResult
from app.schemas.interpretation_graph import GraphSummary
from app.schemas.semantic_fracture import ContextSignal, FractureClassification, FractureRecord


SCHEMA_VERSION = "1.0"


class DatasetArtifact(BaseModel):
    artifact_id: UUID
    sha256: str
    original_name: str
    size_bytes: int
    claimed_extension: str


class DatasetFastScan(BaseModel):
    observed_type: str
    observed_mime: str
    magic_description: str
    extension_matches_observed: bool | None
    entropy: float
    sha256_matches_ingestion: bool
    signals: list[FastScanSignal]


class DatasetInterpretation(BaseModel):
    artifact_family: Literal["PDF", "ZIP", "PNG"]
    interpreters: list[InterpreterResult]
    comparison: InterpretationComparison
    signals: list[DisagreementSignal]


class DatasetFracture(BaseModel):
    fracture_detected: bool
    fracture_count: int
    fracture_types: list[FractureClassification]
    highest_severity: Literal["MEDIUM", "HIGH"] | None
    fractures: list[FractureRecord]
    context_signals: list[ContextSignal]


class GroundTruthProvenance(BaseModel):
    source: Literal["CONTROLLED_HARMLESS_BASELINE", "CONTROLLED_HARMLESS_CLAIM_MISMATCH", "CONTROLLED_DIFFERENTIAL_RESEARCH", "CONTROLLED_SUSPICIOUS_RESEARCH"]
    corpus: Literal["PRISM-CONTROLLED-HARMLESS", "PRISM-DIFFERENTIAL", "PRISM-SUSPICIOUS"]
    corpus_version: Literal["1.0"]
    sample_id: str
    lineage_group_id: str | None = None


SuspiciousReasonCode = Literal[
    "PDF_JAVASCRIPT_ACTION", "PDF_LAUNCH_ACTION", "PDF_RICHMEDIA_CONTENT",
    "ZIP_PATH_TRAVERSAL_ENTRY", "ZIP_ABSOLUTE_PATH_ENTRY",
]


class SuspiciousEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verified: bool
    source: Literal["DETERMINISTIC_SECURITY_OBSERVATION"]
    reason_codes: list[SuspiciousReasonCode]
    evidence_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def verified_requires_reason(self):
        if self.verified and not self.reason_codes:
            raise ValueError("Verified suspicious evidence requires a supported reason code")
        return self


class DatasetRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    sample_id: str
    artifact: DatasetArtifact
    fastscan: DatasetFastScan
    interpretation: DatasetInterpretation
    graph_summary: GraphSummary
    fracture: DatasetFracture
    ground_truth_provenance: GroundTruthProvenance | None = None
    suspicious_evidence: SuspiciousEvidence | None = None


class DatasetExportResult(BaseModel):
    sample_id: str
    artifact_id: UUID
    sha256: str
    fracture_detected: bool
    record_path: str
    status: Literal["EXPORTED"] = "EXPORTED"
