from dataclasses import dataclass

from app.schemas.artifact import ArtifactMetadata
from app.schemas.orchestration import PrismOrchestrationResult
from app.services.suspicious_evidence_service import derive_suspicious_evidence


AMBIGUITY_SIGNALS = {
    "EXTENSION_TYPE_MISMATCH",
    "UNKNOWN_FILE_TYPE",
}


class PrismOrchestrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class DeterministicDeepAnalysisOutcome:
    """Authoritative outcome produced only by deterministic analysis."""

    verified_state: str | None
    ambiguity_observed: bool
    suspicious_verified: bool
    fracture_detected: bool
    reason_codes: tuple[str, ...]


class PrismOrchestrationService:
    def __init__(
        self,
        fastscan_service,
        laya_triage_service,
        interpretation_service,
        interpretation_graph_service,
        semantic_fracture_service,
    ):
        self.fastscan_service = fastscan_service
        self.laya_triage_service = laya_triage_service
        self.interpretation_service = interpretation_service
        self.interpretation_graph_service = interpretation_graph_service
        self.semantic_fracture_service = semantic_fracture_service

    @staticmethod
    def _security_precursor_codes(model_input) -> list[str]:
        features = model_input.pretriage_security_features

        if hasattr(features, "model_dump"):
            features = features.model_dump(mode="python")

        if not isinstance(features, dict):
            return []

        codes = []

        for key, value in features.items():
            if (
                key.endswith("_candidate_count")
                and isinstance(value, (int, float))
                and not isinstance(value, bool)
                and value > 0
            ):
                codes.append(key)

        return sorted(codes)

    def analyze(
        self,
        artifact: ArtifactMetadata,
    ) -> PrismOrchestrationResult:

        # ---------------------------------------------------------
        # Stage 1 — deterministic FastScan
        # ---------------------------------------------------------

        fastscan = self.fastscan_service.get(artifact.artifact_id)

        if fastscan is None:
            fastscan = self.fastscan_service.scan(artifact)

        fastscan_codes = {
            signal.code
            for signal in fastscan.signals
        }

        ambiguity_codes = sorted(
            fastscan_codes.intersection(AMBIGUITY_SIGNALS)
        )

        # ---------------------------------------------------------
        # Stage 2 — learned Laya routing prior
        # ---------------------------------------------------------

        triage = self.laya_triage_service.predict(
            artifact,
            fastscan,
        )

        precursor_codes = self._security_precursor_codes(
            triage.model_input
        )

        reasons = []

        if ambiguity_codes:
            reasons.extend(
                f"FASTSCAN:{code}"
                for code in ambiguity_codes
            )

        if precursor_codes:
            reasons.extend(
                f"SECURITY_PRECURSOR:{code}"
                for code in precursor_codes
            )

        # Laya PASS is allowed only when deterministic pre-triage
        # evidence does not require deeper inspection.
        deep_scan_required = (
            triage.recommended_route != "PASS"
            or bool(ambiguity_codes)
            or bool(precursor_codes)
        )

        if not deep_scan_required:
            return PrismOrchestrationResult(
                artifact_id=artifact.artifact_id,
                triage=triage,
                routing_decision="PASS",
                deep_scan_performed=False,
                verified_state=None,
                ambiguity_observed=False,
                suspicious_verified=None,
                fracture_detected=None,
                reason_codes=["LAYA_PASS_NO_DETERMINISTIC_VETO"],
            )

        # ---------------------------------------------------------
        # Stage 3 — deterministic multi-interpreter analysis
        # ---------------------------------------------------------

        outcome = self.run_deep_analysis(
            artifact,
            fastscan,
            ambiguity_codes=ambiguity_codes,
            reason_codes=reasons,
        )

        routing_decision = (
            "PRISM_LAB"
            if outcome.verified_state is not None
            else "DEEP_SCAN"
        )

        return PrismOrchestrationResult(
            artifact_id=artifact.artifact_id,
            triage=triage,
            routing_decision=routing_decision,
            deep_scan_performed=True,
            verified_state=outcome.verified_state,
            ambiguity_observed=outcome.ambiguity_observed,
            suspicious_verified=outcome.suspicious_verified,
            fracture_detected=outcome.fracture_detected,
            reason_codes=list(outcome.reason_codes),
        )

    def run_deep_analysis(
        self,
        artifact: ArtifactMetadata,
        fastscan,
        *,
        ambiguity_codes: list[str] | tuple[str, ...] | None = None,
        reason_codes: list[str] | tuple[str, ...] | None = None,
    ) -> DeterministicDeepAnalysisOutcome:
        """Run the authoritative deterministic deep-analysis pipeline.

        Laya and Ollama are deliberately absent from this method.
        Normal orchestration and PRISM Lab may both invoke it.
        """

        ambiguity_codes = list(ambiguity_codes or ())
        reasons = list(reason_codes or ())

        family = fastscan.observed.detected_type

        if family not in self.interpretation_service.interpreters:
            raise PrismOrchestrationError(
                f"Unsupported byte-observed artifact family: {family}"
            )

        interpretation = self.interpretation_service.interpret(
            artifact,
            family,
        )

        graph = self.interpretation_graph_service.build(
            artifact,
            fastscan,
            interpretation,
        )

        fracture = self.semantic_fracture_service.analyze(
            artifact,
            fastscan,
            interpretation,
            graph,
        )

        suspicious = derive_suspicious_evidence(
            interpretation,
            artifact.artifact_id,
        )

        suspicious_verified = bool(
            suspicious is not None
            and suspicious.verified
        )

        # Authoritative precedence:
        # FRACTURED > SUSPICIOUS > AMBIGUOUS > no verified state

        if fracture.fracture_detected:
            reasons.append("VERIFIED_SEMANTIC_FRACTURE")

            return DeterministicDeepAnalysisOutcome(
                verified_state="FRACTURED",
                ambiguity_observed=bool(ambiguity_codes),
                suspicious_verified=suspicious_verified,
                fracture_detected=True,
                reason_codes=tuple(reasons),
            )

        if suspicious_verified:
            reasons.append(
                "VERIFIED_DETERMINISTIC_SUSPICIOUS_EVIDENCE"
            )

            if suspicious.reason_codes:
                reasons.extend(
                    f"SUSPICIOUS:{code}"
                    for code in suspicious.reason_codes
                )

            return DeterministicDeepAnalysisOutcome(
                verified_state="SUSPICIOUS",
                ambiguity_observed=bool(ambiguity_codes),
                suspicious_verified=True,
                fracture_detected=False,
                reason_codes=tuple(reasons),
            )

        if ambiguity_codes:
            reasons.append(
                "FASTSCAN_AMBIGUITY_DEEP_SCAN_COMPLETED"
            )

            return DeterministicDeepAnalysisOutcome(
                verified_state=None,
                ambiguity_observed=True,
                suspicious_verified=False,
                fracture_detected=False,
                reason_codes=tuple(reasons),
            )

        reasons.append(
            "DEEP_SCAN_NO_VERIFIED_SECURITY_FINDING"
        )

        return DeterministicDeepAnalysisOutcome(
            verified_state=None,
            ambiguity_observed=False,
            suspicious_verified=False,
            fracture_detected=False,
            reason_codes=tuple(reasons),
        )

