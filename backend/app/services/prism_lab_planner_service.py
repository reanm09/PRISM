from uuid import uuid4

from app.schemas.prism_lab import (
    EXPERIMENT_FAMILIES,
    PrismLabExperimentKind,
    PrismLabExperimentRequest,
)
from app.schemas.prism_lab_planner import (
    PrismLabExperimentPlan,
    PrismLabPlanningResult,
)
from app.schemas.semantic_reasoning import SemanticReasoningResult
from app.schemas.investigation import ArtifactInvestigationState


class PrismLabPlannerError(ValueError):
    pass


class PrismLabPlannerService:
    """Translate typed semantic candidates into allowlisted Lab plans.

    This service never executes experiments and never interprets
    suggested_action as code, commands, or executable instructions.
    """

    def plan(
        self,
        reasoning: SemanticReasoningResult,
        investigation: ArtifactInvestigationState | None = None,
    ) -> PrismLabPlanningResult:
        """
        Legacy semantic-reasoning planning entry point.

        Retained for /reason -> /lab/plan compatibility.
        """
        artifact_id = reasoning.artifact_id

        if reasoning.evidence_summary.artifact_id != artifact_id:
            raise PrismLabPlannerError(
                "Semantic reasoning artifact IDs do not agree"
            )

        if (
            reasoning.evidence_summary.verified_state
            != reasoning.verified_state
        ):
            raise PrismLabPlannerError(
                "Semantic reasoning verified states do not agree"
            )

        return self._plan_proposals(
            artifact_id=artifact_id,
            evidence_summary=reasoning.evidence_summary,
            proposals=reasoning.recommended_experiments,
            investigation=investigation,
        )

    def plan_agent_proposals(
        self,
        evidence_result,
        experiment_result,
        investigation: ArtifactInvestigationState | None = None,
    ) -> PrismLabPlanningResult:
        """
        M6 native planning entry point.

        AI experiment proposals remain non-authoritative.
        This method applies the same deterministic planner policy
        used by the legacy semantic-reasoning path.
        """
        artifact_id = evidence_result.artifact_id

        if evidence_result.evidence.artifact_id != artifact_id:
            raise PrismLabPlannerError(
                "Evidence Agent artifact IDs do not agree"
            )

        if experiment_result.artifact_id != artifact_id:
            raise PrismLabPlannerError(
                "Experiment Agent artifact ID does not agree"
            )

        if (
            experiment_result.investigation_round
            != evidence_result.investigation_round
        ):
            raise PrismLabPlannerError(
                "Experiment Agent investigation round "
                "does not agree with Evidence Agent"
            )

        if (
            evidence_result.evidence.verified_state
            != evidence_result.deterministic_verified_state
        ):
            raise PrismLabPlannerError(
                "Evidence Agent verified states do not agree"
            )

        if investigation is not None:
            if investigation.artifact_id != artifact_id:
                raise PrismLabPlannerError(
                    "Investigation artifact ID does not agree"
                )

            if (
                investigation.investigation_round
                != evidence_result.investigation_round
            ):
                raise PrismLabPlannerError(
                    "Investigation round does not agree with "
                    "Evidence Agent"
                )

            if (
                investigation.verified_state
                != evidence_result.deterministic_verified_state
            ):
                raise PrismLabPlannerError(
                    "Investigation verified state does not agree "
                    "with Evidence Agent"
                )

        return self._plan_proposals(
            artifact_id=artifact_id,
            evidence_summary=evidence_result.evidence,
            proposals=experiment_result.proposed_experiments,
            investigation=investigation,
        )

    def _plan_proposals(
        self,
        *,
        artifact_id,
        evidence_summary,
        proposals,
        investigation: ArtifactInvestigationState | None,
    ) -> PrismLabPlanningResult:
        """
        Single deterministic authorization core shared by legacy
        reasoning and M6 logical-agent planning.
        """
        if evidence_summary.artifact_id != artifact_id:
            raise PrismLabPlannerError(
                "Planner evidence artifact ID does not agree"
            )

        if (
            investigation is not None
            and investigation.artifact_id != artifact_id
        ):
            raise PrismLabPlannerError(
                "Investigation artifact ID does not agree"
            )

        completed_kinds = (
            {
                item.result.experiment_kind
                for item in investigation.completed_experiments
            }
            if investigation
            else set()
        )

        deep_scan_performed = bool(
            evidence_summary.observed.get(
                "deep_scan_performed",
                False,
            )
        )

        observed_family = (
            evidence_summary.observed.get(
                "byte_observed_identity"
            )
        )

        plans: list[PrismLabExperimentPlan] = []

        for index, proposal in enumerate(proposals):
            candidate = proposal.experiment_kind

            base = {
                "plan_id": uuid4(),
                "artifact_id": artifact_id,
                "source_experiment_index": index,
                "candidate_kind": candidate,
                "objective": proposal.objective,
                "rationale": proposal.rationale,
                "suggested_action": (
                    proposal.suggested_action
                ),
                "expected_information_gain": (
                    proposal.expected_information_gain
                ),
            }

            if candidate is None:
                plans.append(
                    PrismLabExperimentPlan(
                        **base,
                        status="REJECTED",
                        rejection_reason=(
                            "MISSING_TYPED_EXPERIMENT_KIND"
                        ),
                    )
                )
                continue

            if candidate == "UNSUPPORTED":
                plans.append(
                    PrismLabExperimentPlan(
                        **base,
                        status="REJECTED",
                        rejection_reason=(
                            "UNSUPPORTED_EXPERIMENT_KIND"
                        ),
                    )
                )
                continue

            if candidate not in EXPERIMENT_FAMILIES:
                plans.append(
                    PrismLabExperimentPlan(
                        **base,
                        status="REJECTED",
                        rejection_reason=(
                            "EXPERIMENT_KIND_NOT_ALLOWLISTED"
                        ),
                    )
                )
                continue

            if candidate in completed_kinds:
                plans.append(
                    PrismLabExperimentPlan(
                        **base,
                        status="REJECTED",
                        rejection_reason=(
                            "EXPERIMENT_ALREADY_COMPLETED"
                        ),
                    )
                )
                continue

            if (
                observed_family
                not in EXPERIMENT_FAMILIES[candidate]
            ):
                plans.append(
                    PrismLabExperimentPlan(
                        **base,
                        status="REJECTED",
                        rejection_reason=(
                            "EXPERIMENT_NOT_SUPPORTED_FOR_ARTIFACT"
                        ),
                    )
                )
                continue

            # A completed deterministic deep interpretation
            # subsumes every currently supported targeted adapter
            # verification. Do not authorize redundant experiments.
            if deep_scan_performed:
                plans.append(
                    PrismLabExperimentPlan(
                        **base,
                        status="REJECTED",
                        rejection_reason=(
                            "DEEP_INTERPRETATION_ALREADY_PERFORMED"
                        ),
                    )
                )
                continue

            if (
                candidate
                != PrismLabExperimentKind.FORCE_DEEP_INTERPRETATION
                and PrismLabExperimentKind.FORCE_DEEP_INTERPRETATION
                in completed_kinds
            ):
                plans.append(
                    PrismLabExperimentPlan(
                        **base,
                        status="REJECTED",
                        rejection_reason=(
                            "DEEP_INTERPRETATION_ALREADY_PERFORMED"
                        ),
                    )
                )
                continue

            # SECURITY BOUNDARY:
            # Only the allowlisted typed enum enters the executable
            # request. suggested_action remains descriptive text.
            request = PrismLabExperimentRequest(
                experiment_kind=candidate,
                hypothesis=proposal.objective,
                rationale=proposal.rationale,
            )

            plans.append(
                PrismLabExperimentPlan(
                    **base,
                    status="PLANNED",
                    experiment_request=request,
                )
            )

        return PrismLabPlanningResult(
            artifact_id=artifact_id,
            plans=plans,
        )
