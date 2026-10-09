from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.prism_lab import (
    PrismLabExperimentKind,
    PrismLabExperimentResult,
)
from app.schemas.rag import RagSource
from app.schemas.semantic_reasoning import (
    ArtifactEvidenceBundle,
    ProposedExperiment,
    SemanticHypothesis,
)


VerifiedState = Literal["SUSPICIOUS", "FRACTURED"] | None


class EvidenceAgentResult(BaseModel):
    """
    Read-only evidence view for one investigation round.

    This role may organize existing evidence, but it cannot create
    authoritative verified state.
    """

    model_config = ConfigDict(frozen=True)

    artifact_id: UUID
    investigation_round: int = Field(ge=0)

    evidence: ArtifactEvidenceBundle

    # Copied only from deterministic Investigation State.
    deterministic_verified_state: VerifiedState

    contradictions: tuple[str, ...] = ()
    evidence_gaps: tuple[str, ...] = ()

    authority: Literal["READ_ONLY_EVIDENCE"] = "READ_ONLY_EVIDENCE"


class HypothesisAgentResult(BaseModel):
    """
    Non-authoritative explanations proposed from available evidence.
    """

    model_config = ConfigDict(frozen=True)

    artifact_id: UUID
    investigation_round: int = Field(ge=0)

    hypotheses: tuple[SemanticHypothesis, ...] = ()
    uncertainties: tuple[str, ...] = ()

    reasoning_summary: str

    sources: tuple[RagSource, ...] = ()

    authority: Literal["ADVISORY"] = "ADVISORY"


class ExperimentAgentResult(BaseModel):
    """
    Typed experiment proposals only.

    This role cannot execute an experiment. Every proposal must still
    pass through the existing server-side PRISM Lab planner.
    """

    model_config = ConfigDict(frozen=True)

    artifact_id: UUID
    investigation_round: int = Field(ge=0)

    proposed_experiments: tuple[ProposedExperiment, ...] = ()

    authority: Literal["PROPOSAL_ONLY"] = "PROPOSAL_ONLY"


class ValidationAssessment(BaseModel):
    """
    Advisory interpretation of how deterministic Lab observations
    relate to the current hypothesis.

    This assessment is never itself verified state.
    """

    model_config = ConfigDict(frozen=True)

    experiment_kind: PrismLabExperimentKind

    assessment: Literal[
        "CONSISTENT",
        "INCONSISTENT",
        "INCONCLUSIVE",
    ]

    rationale: str


class ValidationAgentResult(BaseModel):
    """
    Post-experiment advisory validation.

    experiment_result contains the deterministic Lab result.
    deterministic_verified_state is copied from Investigation State.

    The validation agent cannot manufacture BENIGN, SUSPICIOUS,
    or FRACTURED authority.
    """

    model_config = ConfigDict(frozen=True)

    artifact_id: UUID
    investigation_round: int = Field(ge=0)

    experiment_result: PrismLabExperimentResult

    assessment: ValidationAssessment

    # Must be sourced from accumulated deterministic state.
    deterministic_verified_state: VerifiedState

    authority: Literal["ADVISORY"] = "ADVISORY"
