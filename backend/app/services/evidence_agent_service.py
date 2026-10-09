from app.schemas.investigation_agents import EvidenceAgentResult
from app.schemas.semantic_reasoning import ArtifactEvidenceBundle


class EvidenceAgentError(RuntimeError):
    pass


class EvidenceAgentService:
    """
    Deterministic, read-only evidence organization.

    This service does not:
    - parse artifacts
    - call an LLM
    - execute experiments
    - infer verified state
    - manufacture BENIGN/SUSPICIOUS/FRACTURED authority

    ArtifactEvidenceBundle is expected to have already passed through
    SemanticReasoningService.build_evidence(), which owns the evidence
    integrity checks and deterministic state accumulation.
    """

    def evaluate(
        self,
        evidence: ArtifactEvidenceBundle,
    ) -> EvidenceAgentResult:
        investigation = evidence.investigation

        investigation_round = (
            investigation.investigation_round
            if investigation is not None
            else 0
        )

        contradictions = self._contradictions(evidence)
        evidence_gaps = self._evidence_gaps(evidence)

        return EvidenceAgentResult(
            artifact_id=evidence.artifact_id,
            investigation_round=investigation_round,
            evidence=evidence,
            deterministic_verified_state=evidence.verified_state,
            contradictions=tuple(contradictions),
            evidence_gaps=tuple(evidence_gaps),
        )

    @staticmethod
    def _contradictions(
        evidence: ArtifactEvidenceBundle,
    ) -> list[str]:
        contradictions: list[str] = []

        prediction = evidence.model_prediction.get("state")

        # Model output is advisory. A mismatch is useful investigation
        # context but never changes deterministic authority.
        if (
            evidence.verified_state is not None
            and prediction is not None
            and prediction != evidence.verified_state
        ):
            contradictions.append(
                "MODEL_PREDICTION_DIFFERS_FROM_VERIFIED_STATE"
            )

        investigation = evidence.investigation

        # Investigation State is deterministic history. It must never claim
        # a stronger/different terminal state than the evidence bundle that
        # was constructed from that same accumulated history.
        if (
            investigation is not None
            and investigation.verified_state is not None
            and evidence.verified_state
            != investigation.verified_state
        ):
            raise EvidenceAgentError(
                "Evidence verified state disagrees with "
                "deterministic Investigation State"
            )

        return contradictions

    @staticmethod
    def _evidence_gaps(
        evidence: ArtifactEvidenceBundle,
    ) -> list[str]:
        gaps: list[str] = []

        observed = evidence.observed
        investigation = evidence.investigation

        # analysis.deep_scan_performed describes the INITIAL
        # orchestration decision and must remain historical.
        #
        # A later authoritative PRISM Lab
        # FORCE_DEEP_INTERPRETATION is deterministic evidence
        # that deep interpretation has subsequently occurred.
        lab_deep_interpretation_completed = (
            investigation is not None
            and any(
                getattr(
                    item.result.experiment_kind,
                    "value",
                    item.result.experiment_kind,
                )
                == "FORCE_DEEP_INTERPRETATION"
                for item in investigation.completed_experiments
            )
        )

        initial_deep_interpretation_performed = bool(
            observed.get(
                "deep_scan_performed",
                False,
            )
        )

        if (
            not initial_deep_interpretation_performed
            and not lab_deep_interpretation_completed
        ):
            gaps.append(
                "DEEP_INTERPRETATION_NOT_PERFORMED"
            )

        # INTERPRETER_EVIDENCE_EMPTY applies only when the
        # initial orchestration itself claims deep analysis
        # occurred but supplied no interpreter evidence.
        #
        # A completed Lab FORCE_DEEP is represented through
        # deterministic Investigation State instead; it must
        # not be mistaken for missing initial interpreter data.
        elif (
            initial_deep_interpretation_performed
            and not observed.get("interpreters")
        ):
            gaps.append(
                "INTERPRETER_EVIDENCE_EMPTY"
            )

        if evidence.verified_state is None:
            gaps.append(
                "NO_DETERMINISTIC_VERIFIED_STATE"
            )

        if (
            investigation is None
            or not investigation.completed_experiments
        ):
            gaps.append(
                "NO_COMPLETED_LAB_EXPERIMENTS"
            )

        return gaps
