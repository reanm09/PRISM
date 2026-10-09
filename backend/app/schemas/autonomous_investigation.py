from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.prism_lab import (
    PrismLabExperimentKind,
    PrismLabExperimentResult,
)
from app.schemas.prism_lab_planner import PrismLabPlanningResult
from app.schemas.semantic_reasoning import SemanticReasoningResult
from app.schemas.investigation_agents import (
    EvidenceAgentResult,
    ExperimentAgentResult,
    HypothesisAgentResult,
    ValidationAgentResult,
)


AutonomousInvestigationStatus = Literal[
    "COMPLETED",
    "BOUNDED_STOP",
    "FAILED",
]

AutonomousInvestigationStopReason = Literal[
    "NO_EXPERIMENTS_PROPOSED",
    "NO_EXECUTABLE_PLANS",
    "MAX_ROUNDS_REACHED",
    "MAX_EXPERIMENTS_REACHED",
    "TERMINAL_VERIFIED_STATE",
    "CONTROLLED_FAILURE",
]

VerifiedState = Literal["SUSPICIOUS", "FRACTURED"] | None


class AutonomousInvestigationRound(BaseModel):
    """Auditable record of one bounded autonomous reasoning round."""

    model_config = ConfigDict(frozen=True)

    round_number: int
    # Legacy M5 trace. Present when the controller is
    # intentionally run in backward-compatible reasoning mode.
    reasoning: SemanticReasoningResult | None = None

    # M6 logical-agent trace. These roles are deliberately
    # separate so proposal/advisory output cannot be confused
    # with deterministic authority.
    evidence_agent: EvidenceAgentResult | None = None
    hypothesis_agent: HypothesisAgentResult | None = None
    experiment_agent: ExperimentAgentResult | None = None
    post_experiment_evidence_agent: EvidenceAgentResult | None = None
    validation_agent: ValidationAgentResult | None = None
    planning: PrismLabPlanningResult | None = None

    selected_plan_id: UUID | None = None
    selected_experiment_kind: PrismLabExperimentKind | None = None
    experiment_result: PrismLabExperimentResult | None = None

    outcome: Literal[
        "NO_EXPERIMENTS",
        "NO_EXECUTABLE_PLAN",
        "EXPERIMENT_COMPLETED",
        "TERMINAL_FINDING",
        "FAILED",
    ]


class AutonomousInvestigationResult(BaseModel):
    """Final result of one bounded autonomous investigation run."""

    model_config = ConfigDict(frozen=True)

    artifact_id: UUID
    status: AutonomousInvestigationStatus
    rounds_completed: int
    experiments_executed: int
    stop_reason: AutonomousInvestigationStopReason
    final_verified_state: VerifiedState
    failure_detail: str | None = None
    rounds: tuple[AutonomousInvestigationRound, ...] = ()
