from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.prism_lab import PrismLabExperimentRequest


class PrismLabExperimentPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    plan_id: UUID
    artifact_id: UUID
    source_experiment_index: int

    status: Literal["PLANNED", "REJECTED"]
    candidate_kind: str | None

    objective: str
    rationale: str
    suggested_action: str
    expected_information_gain: str

    experiment_request: PrismLabExperimentRequest | None = None
    rejection_reason: str | None = None


class PrismLabPlanningResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: UUID
    plans: list[PrismLabExperimentPlan]
