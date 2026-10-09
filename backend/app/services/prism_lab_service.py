import hashlib
from uuid import uuid4

from app.interpreters.pdf.pypdf_interpreter import PypdfInterpreter
from app.interpreters.zip.zipfile_interpreter import ZipfileInterpreter

from app.schemas.artifact import ArtifactMetadata
from app.schemas.prism_lab import (
    EXPERIMENT_FAMILIES,
    PrismLabExperimentKind,
    PrismLabExperimentRequest,
    PrismLabExperimentResult,
)
from app.services.prism_orchestration_service import (
    AMBIGUITY_SIGNALS,
    PrismOrchestrationService,
)


class PrismLabError(RuntimeError):
    pass


class PrismLabService:
    """Executes only explicitly allowlisted deterministic experiments."""

    def __init__(
        self,
        fastscan_service,
        orchestration_service: PrismOrchestrationService,
    ):
        self.fastscan_service = fastscan_service
        self.orchestration_service = orchestration_service

    def run(
        self,
        artifact: ArtifactMetadata,
        request: PrismLabExperimentRequest,
    ) -> PrismLabExperimentResult:
        if request.experiment_kind not in EXPERIMENT_FAMILIES:
            raise PrismLabError(
                f"Unsupported PRISM Lab experiment: {request.experiment_kind}"
            )

        # Follow normal orchestration behavior: obtain existing FastScan
        # evidence or deterministically produce it if it does not yet exist.
        fastscan = self.fastscan_service.get(artifact.artifact_id)

        if fastscan is None:
            fastscan = self.fastscan_service.scan(artifact)

        family = fastscan.observed.detected_type
        if family not in EXPERIMENT_FAMILIES[request.experiment_kind]:
            raise PrismLabError(
                f"{request.experiment_kind} is not supported for {family} artifacts"
            )

        if request.experiment_kind != PrismLabExperimentKind.FORCE_DEEP_INTERPRETATION:
            path = self.fastscan_service.storage / str(artifact.artifact_id)
            digest = hashlib.sha256()
            with path.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
            if digest.hexdigest() != artifact.sha256 or fastscan.sha256 != artifact.sha256:
                raise PrismLabError("Stored artifact SHA-256 differs from investigation evidence")

            adapter = (PypdfInterpreter() if request.experiment_kind
                       == PrismLabExperimentKind.VERIFY_PDF_ACTIONS else ZipfileInterpreter())
            try:
                parsed = adapter.interpret(path)
            except Exception as exc:
                raise PrismLabError(
                    f"{request.experiment_kind} parser inspection failed: {type(exc).__name__}"
                ) from exc
            fields = (
                ("javascript_action_count", "launch_action_count", "richmedia_count")
                if request.experiment_kind == PrismLabExperimentKind.VERIFY_PDF_ACTIONS
                else ("entry_count", "path_traversal_entry_count", "absolute_path_entry_count")
            )
            observations = {
                "recognized": parsed.recognized, "valid": parsed.valid,
                **{name: getattr(parsed.observations, name) for name in fields},
            }
            return PrismLabExperimentResult(
                experiment_id=uuid4(), artifact_id=artifact.artifact_id,
                experiment_kind=request.experiment_kind, status="COMPLETED",
                deterministic=True, deep_scan_performed=False,
                hypothesis=request.hypothesis, rationale=request.rationale,
                verified_state=None, ambiguity_observed=any(
                    signal.code in AMBIGUITY_SIGNALS for signal in fastscan.signals
                ),
                suspicious_verified=False, fracture_detected=False,
                reason_codes=[f"LAB:{request.experiment_kind.value}"],
                observations=observations,
            )

        fastscan_codes = {
            signal.code
            for signal in fastscan.signals
        }

        ambiguity_codes = sorted(
            fastscan_codes.intersection(AMBIGUITY_SIGNALS)
        )

        # IMPORTANT:
        # hypothesis and rationale are provenance only.
        # They are never passed into deterministic analysis.
        outcome = self.orchestration_service.run_deep_analysis(
            artifact,
            fastscan,
            ambiguity_codes=ambiguity_codes,
            reason_codes=["LAB:FORCE_DEEP_INTERPRETATION"],
        )

        return PrismLabExperimentResult(
            experiment_id=uuid4(),
            artifact_id=artifact.artifact_id,
            experiment_kind=request.experiment_kind,
            status="COMPLETED",
            deterministic=True,
            deep_scan_performed=True,
            hypothesis=request.hypothesis,
            rationale=request.rationale,
            verified_state=outcome.verified_state,
            ambiguity_observed=outcome.ambiguity_observed,
            suspicious_verified=outcome.suspicious_verified,
            fracture_detected=outcome.fracture_detected,
            reason_codes=list(outcome.reason_codes),
        )
