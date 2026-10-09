from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.rag import RagSource
from app.schemas.investigation import ArtifactInvestigationState


class ContainmentEvidence(BaseModel):
    """Read-only containment facts exposed to Evidence Intelligence.

    Containment is a protective system action. It is never itself
    authoritative proof of an artifact security state.
    """

    status: Literal["QUARANTINED", "RESTORED"]
    trigger: Literal[
        "LAYA_SUSPICIOUS",
        "DETERMINISTIC_SUSPICIOUS",
    ]

    laya_prediction: str | None = None
    laya_confidence: float | None = None

    verified_state: Literal[
        "FRACTURED",
        "SUSPICIOUS",
    ] | None = None

    reason_codes: list[str] = Field(default_factory=list)

    quarantined_at: datetime
    restored_at: datetime | None = None


class ArtifactEvidenceBundle(BaseModel):
    artifact_id: UUID
    sha256: str
    observed: dict[str, Any]
    model_prediction: dict[str, Any]
    verified_findings: dict[str, Any]
    routing_decision: str
    verified_state: Literal["FRACTURED", "SUSPICIOUS"] | None
    investigation: ArtifactInvestigationState | None = None
    containment: ContainmentEvidence | None = None


class SemanticHypothesis(BaseModel):
    statement: str = Field(max_length=600)
    rationale: str = Field(max_length=800)
    supporting_evidence: list[str] = Field(default_factory=list, max_length=5)


class ProposedExperiment(BaseModel):
    experiment_kind: Literal[
        "FORCE_DEEP_INTERPRETATION",
        "VERIFY_PDF_ACTIONS",
        "VERIFY_ZIP_ENTRY_PATHS",
        "UNSUPPORTED",
    ] | None = None

    objective: str = Field(max_length=500)
    rationale: str = Field(max_length=800)
    suggested_action: str = Field(max_length=500)
    expected_information_gain: str = Field(max_length=500)


class SemanticReasoningPayload(BaseModel):
    reasoning_summary: str = Field(max_length=2000)
    hypotheses: list[SemanticHypothesis] = Field(default_factory=list, max_length=5)
    uncertainties: list[str] = Field(default_factory=list, max_length=5)
    recommended_experiments: list[ProposedExperiment] = Field(default_factory=list, max_length=5)


class InterpreterComparisonSummary(BaseModel):
    total_properties: int = 0
    agreement_count: int = 0
    disagreement_count: int = 0
    not_comparable_count: int = 0

    status: Literal[
        "NOT_AVAILABLE",
        "COMPARABLE_PROPERTIES_AGREE",
        "DISAGREEMENT_PRESENT",
        "PARTIAL_COMPARABILITY",
    ] = "NOT_AVAILABLE"


class ReasoningTraceStep(BaseModel):
    sequence: int
    stage: str
    authority: Literal[
        "DETERMINISTIC",
        "MODEL_ADVISORY",
        "SYSTEM_ACTION",
    ]
    summary: str
    evidence_codes: list[str] = Field(default_factory=list)


class ExperimentHistoryEntry(BaseModel):
    experiment_kind: str
    status: str
    deterministic: bool
    deep_scan_performed: bool
    verified_state: Literal["FRACTURED", "SUSPICIOUS"] | None = None
    reason_codes: list[str] = Field(default_factory=list)


class KnowledgeReference(BaseModel):
    title: str
    document: str
    chunk_id: str


class SemanticReasoningResult(SemanticReasoningPayload):
    artifact_id: UUID
    evidence_summary: ArtifactEvidenceBundle
    retrieval_query: str
    sources: list[RagSource]
    verified_state: Literal["FRACTURED", "SUSPICIOUS"] | None

    # Deterministic Evidence Intelligence.
    comparison_summary: InterpreterComparisonSummary | None = None
    why_prism_reached_state: list[ReasoningTraceStep] = Field(
        default_factory=list
    )
    experiment_history: list[ExperimentHistoryEntry] = Field(
        default_factory=list
    )
    knowledge_references: list[KnowledgeReference] = Field(
        default_factory=list
    )
