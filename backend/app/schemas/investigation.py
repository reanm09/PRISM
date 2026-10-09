from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.prism_lab import PrismLabExperimentResult


VerifiedState = Literal["SUSPICIOUS", "FRACTURED"] | None


class CompletedLabExperiment(BaseModel):
    model_config = ConfigDict(frozen=True)

    plan_id: UUID
    result: PrismLabExperimentResult


class ArtifactInvestigationState(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: UUID
    investigation_round: int = 0
    completed_experiments: tuple[CompletedLabExperiment, ...] = ()
    verified_state: VerifiedState = None
    latest_lab_result: PrismLabExperimentResult | None = None


def stronger_verified_state(first: VerifiedState, second: VerifiedState) -> VerifiedState:
    order = {None: 0, "SUSPICIOUS": 1, "FRACTURED": 2}
    return first if order[first] >= order[second] else second


def record_completed_experiment(
    state: ArtifactInvestigationState,
    plan_id: UUID,
    result: PrismLabExperimentResult,
) -> ArtifactInvestigationState:
    if result.artifact_id != state.artifact_id:
        raise ValueError("Lab result artifact mismatch")
    if any(item.plan_id == plan_id or item.result.experiment_id == result.experiment_id
           for item in state.completed_experiments):
        raise ValueError("Lab experiment has already been recorded")
    completed = CompletedLabExperiment(plan_id=plan_id, result=result)
    return ArtifactInvestigationState(
        artifact_id=state.artifact_id,
        investigation_round=state.investigation_round + 1,
        completed_experiments=(*state.completed_experiments, completed),
        verified_state=stronger_verified_state(state.verified_state, result.verified_state),
        latest_lab_result=result,
    )
