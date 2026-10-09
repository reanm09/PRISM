from collections.abc import Callable
from uuid import UUID

from app.schemas.autonomous_investigation import (
    AutonomousInvestigationResult,
    AutonomousInvestigationRound,
)
from app.schemas.investigation import ArtifactInvestigationState
from app.schemas.prism_lab import PrismLabExperimentResult
from app.schemas.prism_lab_planner import PrismLabPlanningResult
from app.schemas.semantic_reasoning import SemanticReasoningResult


MAX_AUTONOMOUS_ROUNDS = 4
MAX_AUTONOMOUS_EXPERIMENTS = 3


class AutonomousInvestigationService:
    """Coordinate a bounded reason -> plan -> execute -> observe loop.

    This service does not create evidence, plans, or experiment requests.
    Those remain owned by the existing Semantic Reasoning, planner, and
    authoritative Lab execution paths.
    """

    def __init__(
        self,
        *,
        reason: Callable | None = None,
        plan: Callable | None = None,
        evidence: Callable | None = None,
        hypothesize: Callable | None = None,
        propose: Callable | None = None,
        plan_agents: Callable | None = None,
        validate: Callable | None = None,
        execute: Callable[[UUID, UUID], PrismLabExperimentResult],
        get_investigation: Callable[[UUID], ArtifactInvestigationState],
        controlled_error_types: tuple[type[Exception], ...] = (),
        max_rounds: int = MAX_AUTONOMOUS_ROUNDS,
        max_experiments: int = MAX_AUTONOMOUS_EXPERIMENTS,
    ):
        if max_rounds < 1 or max_experiments < 1:
            raise ValueError(
                "Autonomous investigation bounds "
                "must be positive"
            )

        if max_rounds > MAX_AUTONOMOUS_ROUNDS:
            raise ValueError(
                "max_rounds exceeds server maximum"
            )

        if max_experiments > MAX_AUTONOMOUS_EXPERIMENTS:
            raise ValueError(
                "max_experiments exceeds server maximum"
            )

        legacy_enabled = (
            reason is not None
            and plan is not None
        )

        m6_callbacks = (
            evidence,
            hypothesize,
            propose,
            plan_agents,
            validate,
        )

        m6_enabled = all(
            callback is not None
            for callback in m6_callbacks
        )

        partially_configured_m6 = (
            any(
                callback is not None
                for callback in m6_callbacks
            )
            and not m6_enabled
        )

        if partially_configured_m6:
            raise ValueError(
                "M6 autonomous investigation requires "
                "evidence, hypothesize, propose, "
                "plan_agents, and validate callbacks"
            )

        if not legacy_enabled and not m6_enabled:
            raise ValueError(
                "Autonomous investigation requires either "
                "legacy reason/plan callbacks or the complete "
                "M6 logical-agent pipeline"
            )

        self._reason = reason
        self._plan = plan

        self._evidence = evidence
        self._hypothesize = hypothesize
        self._propose = propose
        self._plan_agents = plan_agents
        self._validate = validate

        self._m6_enabled = m6_enabled

        self._execute = execute
        self._get_investigation = (
            get_investigation
        )

        self._controlled_error_types = (
            controlled_error_types
        )

        self.max_rounds = max_rounds
        self.max_experiments = max_experiments

    def run(
        self,
        artifact_id: UUID,
    ) -> AutonomousInvestigationResult:
        if self._m6_enabled:
            return self._run_m6(
                artifact_id
            )

        return self._run_legacy(
            artifact_id
        )

    def _run_m6(
        self,
        artifact_id: UUID,
    ) -> AutonomousInvestigationResult:
        rounds: list[
            AutonomousInvestigationRound
        ] = []

        experiments_executed = 0

        state = self._get_investigation(
            artifact_id
        )

        # Only accumulated deterministic state may cause
        # a terminal verified-state stop.
        if state.verified_state in {
            "FRACTURED",
            "SUSPICIOUS",
        }:
            return self._result(
                artifact_id=artifact_id,
                status="COMPLETED",
                stop_reason=(
                    "TERMINAL_VERIFIED_STATE"
                ),
                rounds=rounds,
                experiments_executed=(
                    experiments_executed
                ),
                state=state,
            )

        for round_number in range(
            1,
            self.max_rounds + 1,
        ):
            # -----------------------------------------
            # EVIDENCE AGENT
            # -----------------------------------------
            try:
                evidence = self._evidence(
                    artifact_id
                )

                hypothesis = self._hypothesize(
                    evidence
                )

                experiment_agent = self._propose(
                    evidence,
                    hypothesis,
                )

            except Exception as exc:
                if not self._is_controlled(exc):
                    raise

                return self._failed(
                    artifact_id,
                    rounds,
                    experiments_executed,
                    exc,
                )

            # -----------------------------------------
            # No proposal = deterministic bounded stop.
            # -----------------------------------------
            if (
                not experiment_agent
                .proposed_experiments
            ):
                rounds.append(
                    AutonomousInvestigationRound(
                        round_number=round_number,
                        evidence_agent=evidence,
                        hypothesis_agent=hypothesis,
                        experiment_agent=(
                            experiment_agent
                        ),
                        outcome="NO_EXPERIMENTS",
                    )
                )

                state = self._get_investigation(
                    artifact_id
                )

                return self._result(
                    artifact_id=artifact_id,
                    status="COMPLETED",
                    stop_reason=(
                        "NO_EXPERIMENTS_PROPOSED"
                    ),
                    rounds=rounds,
                    experiments_executed=(
                        experiments_executed
                    ),
                    state=state,
                )

            # -----------------------------------------
            # DETERMINISTIC PLANNER AUTHORIZATION
            # -----------------------------------------
            try:
                planning = self._plan_agents(
                    evidence,
                    experiment_agent,
                )

            except Exception as exc:
                if not self._is_controlled(exc):
                    raise

                rounds.append(
                    AutonomousInvestigationRound(
                        round_number=round_number,
                        evidence_agent=evidence,
                        hypothesis_agent=hypothesis,
                        experiment_agent=(
                            experiment_agent
                        ),
                        outcome="FAILED",
                    )
                )

                return self._failed(
                    artifact_id,
                    rounds,
                    experiments_executed,
                    exc,
                )

            # Proposal order remains authoritative only
            # for selection order. Authorization belongs
            # to the deterministic planner.
            selected = next(
                (
                    plan
                    for plan in planning.plans
                    if plan.status == "PLANNED"
                ),
                None,
            )

            if selected is None:
                rounds.append(
                    AutonomousInvestigationRound(
                        round_number=round_number,
                        evidence_agent=evidence,
                        hypothesis_agent=hypothesis,
                        experiment_agent=(
                            experiment_agent
                        ),
                        planning=planning,
                        outcome=(
                            "NO_EXECUTABLE_PLAN"
                        ),
                    )
                )

                state = self._get_investigation(
                    artifact_id
                )

                return self._result(
                    artifact_id=artifact_id,
                    status="COMPLETED",
                    stop_reason=(
                        "NO_EXECUTABLE_PLANS"
                    ),
                    rounds=rounds,
                    experiments_executed=(
                        experiments_executed
                    ),
                    state=state,
                )

            if (
                selected.experiment_request
                is None
            ):
                raise RuntimeError(
                    "PLANNED Lab plan has no "
                    "authorized experiment request"
                )

            # -----------------------------------------
            # AUTHORITATIVE LAB EXECUTION
            # -----------------------------------------
            try:
                result = self._execute(
                    artifact_id,
                    selected.plan_id,
                )

            except Exception as exc:
                if not self._is_controlled(exc):
                    raise

                rounds.append(
                    AutonomousInvestigationRound(
                        round_number=round_number,
                        evidence_agent=evidence,
                        hypothesis_agent=hypothesis,
                        experiment_agent=(
                            experiment_agent
                        ),
                        planning=planning,
                        selected_plan_id=(
                            selected.plan_id
                        ),
                        selected_experiment_kind=(
                            selected
                            .experiment_request
                            .experiment_kind
                        ),
                        outcome="FAILED",
                    )
                )

                return self._failed(
                    artifact_id,
                    rounds,
                    experiments_executed,
                    exc,
                )

            experiments_executed += 1

            # Never derive authority from the proposal,
            # validation model, or local result object.
            state = self._get_investigation(
                artifact_id
            )

            terminal = (
                state.verified_state
                in {
                    "FRACTURED",
                    "SUSPICIOUS",
                }
            )

            # -----------------------------------------
            # REFRESH DETERMINISTIC EVIDENCE
            # -----------------------------------------
            try:
                post_evidence = self._evidence(
                    artifact_id
                )

                validation = self._validate(
                    post_evidence,
                    hypothesis,
                    result,
                )

            except Exception as exc:
                if not self._is_controlled(exc):
                    raise

                # A deterministic terminal finding cannot
                # be erased or downgraded by advisory
                # Validation Agent failure.
                if terminal:
                    rounds.append(
                        AutonomousInvestigationRound(
                            round_number=round_number,
                            evidence_agent=evidence,
                            hypothesis_agent=(
                                hypothesis
                            ),
                            experiment_agent=(
                                experiment_agent
                            ),
                            planning=planning,
                            selected_plan_id=(
                                selected.plan_id
                            ),
                            selected_experiment_kind=(
                                selected
                                .experiment_request
                                .experiment_kind
                            ),
                            experiment_result=result,
                            outcome=(
                                "TERMINAL_FINDING"
                            ),
                        )
                    )

                    return self._result(
                        artifact_id=artifact_id,
                        status="COMPLETED",
                        stop_reason=(
                            "TERMINAL_VERIFIED_STATE"
                        ),
                        rounds=rounds,
                        experiments_executed=(
                            experiments_executed
                        ),
                        state=state,
                    )

                rounds.append(
                    AutonomousInvestigationRound(
                        round_number=round_number,
                        evidence_agent=evidence,
                        hypothesis_agent=hypothesis,
                        experiment_agent=(
                            experiment_agent
                        ),
                        planning=planning,
                        selected_plan_id=(
                            selected.plan_id
                        ),
                        selected_experiment_kind=(
                            selected
                            .experiment_request
                            .experiment_kind
                        ),
                        experiment_result=result,
                        outcome="FAILED",
                    )
                )

                return self._failed(
                    artifact_id,
                    rounds,
                    experiments_executed,
                    exc,
                )

            rounds.append(
                AutonomousInvestigationRound(
                    round_number=round_number,
                    evidence_agent=evidence,
                    hypothesis_agent=hypothesis,
                    experiment_agent=(
                        experiment_agent
                    ),
                    planning=planning,
                    selected_plan_id=(
                        selected.plan_id
                    ),
                    selected_experiment_kind=(
                        selected
                        .experiment_request
                        .experiment_kind
                    ),
                    experiment_result=result,
                    post_experiment_evidence_agent=(
                        post_evidence
                    ),
                    validation_agent=validation,
                    outcome=(
                        "TERMINAL_FINDING"
                        if terminal
                        else "EXPERIMENT_COMPLETED"
                    ),
                )
            )

            if terminal:
                return self._result(
                    artifact_id=artifact_id,
                    status="COMPLETED",
                    stop_reason=(
                        "TERMINAL_VERIFIED_STATE"
                    ),
                    rounds=rounds,
                    experiments_executed=(
                        experiments_executed
                    ),
                    state=state,
                )

            if (
                experiments_executed
                >= self.max_experiments
            ):
                return self._result(
                    artifact_id=artifact_id,
                    status="BOUNDED_STOP",
                    stop_reason=(
                        "MAX_EXPERIMENTS_REACHED"
                    ),
                    rounds=rounds,
                    experiments_executed=(
                        experiments_executed
                    ),
                    state=state,
                )

        state = self._get_investigation(
            artifact_id
        )

        return self._result(
            artifact_id=artifact_id,
            status="BOUNDED_STOP",
            stop_reason="MAX_ROUNDS_REACHED",
            rounds=rounds,
            experiments_executed=(
                experiments_executed
            ),
            state=state,
        )

    def _run_legacy(self, artifact_id: UUID) -> AutonomousInvestigationResult:
        rounds: list[AutonomousInvestigationRound] = []
        experiments_executed = 0

        state = self._get_investigation(artifact_id)

        # Only deterministic accumulated state may cause this terminal stop.
        if state.verified_state in {"FRACTURED", "SUSPICIOUS"}:
            return self._result(
                artifact_id=artifact_id,
                status="COMPLETED",
                stop_reason="TERMINAL_VERIFIED_STATE",
                rounds=rounds,
                experiments_executed=experiments_executed,
                state=state,
            )

        for round_number in range(1, self.max_rounds + 1):
            # -------------------------------------------------
            # REASON
            # -------------------------------------------------
            try:
                reasoning = self._reason(artifact_id)
            except Exception as exc:
                if not self._is_controlled(exc):
                    raise

                return self._failed(
                    artifact_id,
                    rounds,
                    experiments_executed,
                    exc,
                )

            if not reasoning.recommended_experiments:
                rounds.append(
                    AutonomousInvestigationRound(
                        round_number=round_number,
                        reasoning=reasoning,
                        outcome="NO_EXPERIMENTS",
                    )
                )

                state = self._get_investigation(artifact_id)

                return self._result(
                    artifact_id=artifact_id,
                    status="COMPLETED",
                    stop_reason="NO_EXPERIMENTS_PROPOSED",
                    rounds=rounds,
                    experiments_executed=experiments_executed,
                    state=state,
                )

            # -------------------------------------------------
            # PLAN
            # -------------------------------------------------
            try:
                planning = self._plan(artifact_id, reasoning)
            except Exception as exc:
                if not self._is_controlled(exc):
                    raise

                rounds.append(
                    AutonomousInvestigationRound(
                        round_number=round_number,
                        reasoning=reasoning,
                        outcome="FAILED",
                    )
                )

                return self._failed(
                    artifact_id,
                    rounds,
                    experiments_executed,
                    exc,
                )

            # Proposal order is authoritative for controller selection.
            # We execute at most the first PLANNED experiment this round.
            selected = next(
                (
                    plan
                    for plan in planning.plans
                    if plan.status == "PLANNED"
                ),
                None,
            )

            if selected is None:
                rounds.append(
                    AutonomousInvestigationRound(
                        round_number=round_number,
                        reasoning=reasoning,
                        planning=planning,
                        outcome="NO_EXECUTABLE_PLAN",
                    )
                )

                state = self._get_investigation(artifact_id)

                return self._result(
                    artifact_id=artifact_id,
                    status="COMPLETED",
                    stop_reason="NO_EXECUTABLE_PLANS",
                    rounds=rounds,
                    experiments_executed=experiments_executed,
                    state=state,
                )

            # A PLANNED result without an authorized typed request is an
            # internal integrity error, not something the controller repairs.
            if selected.experiment_request is None:
                raise RuntimeError(
                    "PLANNED Lab plan has no authorized experiment request"
                )

            # -------------------------------------------------
            # EXECUTE
            # -------------------------------------------------
            try:
                result = self._execute(
                    artifact_id,
                    selected.plan_id,
                )
            except Exception as exc:
                if not self._is_controlled(exc):
                    raise

                rounds.append(
                    AutonomousInvestigationRound(
                        round_number=round_number,
                        reasoning=reasoning,
                        planning=planning,
                        selected_plan_id=selected.plan_id,
                        selected_experiment_kind=(
                            selected.experiment_request.experiment_kind
                        ),
                        outcome="FAILED",
                    )
                )

                return self._failed(
                    artifact_id,
                    rounds,
                    experiments_executed,
                    exc,
                )

            experiments_executed += 1

            # Never derive authority from the LLM or from the controller's
            # local result object. Re-read accumulated deterministic state.
            state = self._get_investigation(artifact_id)

            terminal = state.verified_state in {
                "FRACTURED",
                "SUSPICIOUS",
            }

            rounds.append(
                AutonomousInvestigationRound(
                    round_number=round_number,
                    reasoning=reasoning,
                    planning=planning,
                    selected_plan_id=selected.plan_id,
                    selected_experiment_kind=(
                        selected.experiment_request.experiment_kind
                    ),
                    experiment_result=result,
                    outcome=(
                        "TERMINAL_FINDING"
                        if terminal
                        else "EXPERIMENT_COMPLETED"
                    ),
                )
            )

            if terminal:
                return self._result(
                    artifact_id=artifact_id,
                    status="COMPLETED",
                    stop_reason="TERMINAL_VERIFIED_STATE",
                    rounds=rounds,
                    experiments_executed=experiments_executed,
                    state=state,
                )

            if experiments_executed >= self.max_experiments:
                return self._result(
                    artifact_id=artifact_id,
                    status="BOUNDED_STOP",
                    stop_reason="MAX_EXPERIMENTS_REACHED",
                    rounds=rounds,
                    experiments_executed=experiments_executed,
                    state=state,
                )

        state = self._get_investigation(artifact_id)

        return self._result(
            artifact_id=artifact_id,
            status="BOUNDED_STOP",
            stop_reason="MAX_ROUNDS_REACHED",
            rounds=rounds,
            experiments_executed=experiments_executed,
            state=state,
        )

    def _is_controlled(self, exc: Exception) -> bool:
        return bool(self._controlled_error_types) and isinstance(
            exc,
            self._controlled_error_types,
        )

    def _failed(
        self,
        artifact_id: UUID,
        rounds: list[AutonomousInvestigationRound],
        experiments_executed: int,
        exc: Exception,
    ) -> AutonomousInvestigationResult:
        state = self._get_investigation(artifact_id)

        return self._result(
            artifact_id=artifact_id,
            status="FAILED",
            stop_reason="CONTROLLED_FAILURE",
            rounds=rounds,
            experiments_executed=experiments_executed,
            state=state,
            failure_detail=f"{type(exc).__name__}: {exc}",
        )

    @staticmethod
    def _result(
        *,
        artifact_id: UUID,
        status: str,
        stop_reason: str,
        rounds: list[AutonomousInvestigationRound],
        experiments_executed: int,
        state: ArtifactInvestigationState,
        failure_detail: str | None = None,
    ) -> AutonomousInvestigationResult:
        return AutonomousInvestigationResult(
            artifact_id=artifact_id,
            status=status,
            rounds_completed=len(rounds),
            experiments_executed=experiments_executed,
            stop_reason=stop_reason,
            final_verified_state=state.verified_state,
            failure_detail=failure_detail,
            rounds=tuple(rounds),
        )
