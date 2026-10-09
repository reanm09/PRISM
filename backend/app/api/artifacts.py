from threading import Lock
from uuid import UUID

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.core.config import settings
from app.schemas.artifact import ArtifactMetadata
from app.schemas.fastscan import FastScanResult
from app.schemas.fracture_dataset import DatasetExportResult
from app.schemas.interpretation import InterpretationResult
from app.schemas.interpretation_graph import InterpretationGraph
from app.schemas.laya_triage import LayaTriageResult
from app.schemas.semantic_fracture import SemanticFractureResult
from app.services.artifact_service import (
    ArtifactService,
    ArtifactTooLargeError,
    EmptyArtifactError,
)
from app.services.fastscan_service import FastScanService
from app.services.fracture_dataset_service import DatasetEvidenceError, FractureDatasetService
from app.services.interpretation_service import InterpretationService
from app.services.interpretation_graph_service import InterpretationGraphService
from app.services.laya_triage_service import LayaTriageError, LayaTriageService
from app.services.semantic_fracture_service import EvidenceIntegrityError, SemanticFractureService
from app.schemas.orchestration import PrismOrchestrationResult
from app.services.prism_orchestration_service import PrismOrchestrationError, PrismOrchestrationService
from app.schemas.semantic_reasoning import SemanticReasoningResult
from app.schemas.autonomous_investigation import AutonomousInvestigationResult
from app.services.autonomous_investigation_service import AutonomousInvestigationService
from app.schemas.prism_lab import PrismLabExperimentResult
from app.services.prism_lab_service import PrismLabError, PrismLabService
from app.schemas.prism_lab_planner import (
    PrismLabExperimentPlan,
    PrismLabPlanningResult,
)
from app.schemas.investigation import (
    ArtifactInvestigationState,
    record_completed_experiment,
    stronger_verified_state,
)
from app.services.prism_lab_planner_service import (
    PrismLabPlannerError,
    PrismLabPlannerService,
)
from app.services.semantic_reasoning_service import SemanticReasoningError, SemanticReasoningService
from app.services.quarantine_runtime import quarantine_service
from app.services.rag.service import RagIndexError
from app.services.rag.runtime import rag_service
from app.services.rag.models import RagModelError
from app.services.evidence_agent_service import EvidenceAgentService
from app.services.hypothesis_agent_service import HypothesisAgentService
from app.services.experiment_agent_service import ExperimentAgentService
from app.services.validation_agent_service import ValidationAgentService


router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])
artifact_service = ArtifactService(settings)
fastscan_service = FastScanService(settings.artifact_storage)
interpretation_service = InterpretationService(settings.artifact_storage, settings.max_upload_bytes)
interpretation_graph_service = InterpretationGraphService()
laya_triage_service = LayaTriageService()
semantic_fracture_service = SemanticFractureService()

prism_orchestration_service = PrismOrchestrationService(
    fastscan_service=fastscan_service,
    laya_triage_service=laya_triage_service,
    interpretation_service=interpretation_service,
    interpretation_graph_service=interpretation_graph_service,
    semantic_fracture_service=semantic_fracture_service,
)

fracture_dataset_service = FractureDatasetService(settings.fracture_root)
semantic_reasoning_service = SemanticReasoningService(rag_service)
prism_lab_service = PrismLabService(
    fastscan_service=fastscan_service,
    orchestration_service=prism_orchestration_service,
)
prism_lab_planner_service = PrismLabPlannerService()

# M6 logical investigation roles.
# One local reasoning runtime may serve multiple advisory roles,
# but each role has a separate typed contract and authority.
evidence_agent_service = EvidenceAgentService()
hypothesis_agent_service = HypothesisAgentService(rag_service)
experiment_agent_service = ExperimentAgentService(rag_service)
validation_agent_service = ValidationAgentService(rag_service)

_analysis_results: dict[UUID, PrismOrchestrationResult] = {}
_reasoning_results: dict[UUID, SemanticReasoningResult] = {}
_lab_plans: dict[UUID, PrismLabExperimentPlan] = {}
_executed_lab_plan_ids: set[UUID] = set()
_lab_results: dict[UUID, PrismLabExperimentResult] = {}
_investigation_states: dict[UUID, ArtifactInvestigationState] = {}

_autonomous_investigations_running: set[UUID] = set()
_autonomous_investigation_guard = Lock()


def _investigation_for(artifact_id: UUID) -> ArtifactInvestigationState:
    state = _investigation_states.get(artifact_id)
    initial = _analysis_results.get(artifact_id)
    initial_verified = initial.verified_state if initial is not None else None
    if state is None:
        return ArtifactInvestigationState(artifact_id=artifact_id, verified_state=initial_verified)
    accumulated = stronger_verified_state(state.verified_state, initial_verified)
    return state if accumulated == state.verified_state else state.model_copy(
        update={"verified_state": accumulated}
    )


@router.post("", response_model=ArtifactMetadata, status_code=status.HTTP_201_CREATED)
async def ingest_artifact(file: UploadFile) -> ArtifactMetadata:
    try:
        return await artifact_service.ingest(file)
    except EmptyArtifactError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ArtifactTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Artifact storage failed") from exc


@router.get("/{artifact_id}", response_model=ArtifactMetadata)
async def get_artifact(artifact_id: UUID) -> ArtifactMetadata:
    metadata = artifact_service.get(artifact_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return metadata


@router.post("/{artifact_id}/fastscan", response_model=FastScanResult)
def run_fastscan(artifact_id: UUID) -> FastScanResult:
    metadata = artifact_service.get(artifact_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    try:
        return fastscan_service.scan(metadata)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Stored artifact not found") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Artifact read failed") from exc


@router.get("/{artifact_id}/fastscan", response_model=FastScanResult)
def get_fastscan(artifact_id: UUID) -> FastScanResult:
    if artifact_service.get(artifact_id) is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    result = fastscan_service.get(artifact_id)
    if result is None:
        raise HTTPException(status_code=404, detail="FastScan has not been performed")
    return result



@router.post("/{artifact_id}/triage", response_model=LayaTriageResult)
def run_laya_triage(artifact_id: UUID) -> LayaTriageResult:
    metadata = artifact_service.get(artifact_id)

    if metadata is None:
        raise HTTPException(
            status_code=404,
            detail="Artifact not found",
        )

    fastscan = fastscan_service.get(artifact_id)

    if fastscan is None:
        raise HTTPException(
            status_code=409,
            detail="FastScan must be performed first",
        )

    try:
        return laya_triage_service.predict(
            metadata,
            fastscan,
        )

    except LayaTriageError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc


@router.get("/{artifact_id}/triage", response_model=LayaTriageResult)
def get_laya_triage(artifact_id: UUID) -> LayaTriageResult:

    if artifact_service.get(artifact_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Artifact not found",
        )

    result = laya_triage_service.get(
        artifact_id
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Laya triage has not been performed",
        )

    return result


@router.post("/{artifact_id}/interpret", response_model=InterpretationResult)
def interpret_artifact(artifact_id: UUID) -> InterpretationResult:
    metadata = artifact_service.get(artifact_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    fastscan = fastscan_service.get(artifact_id)
    if fastscan is None:
        raise HTTPException(status_code=409, detail="FastScan must be performed first")
    family = fastscan.observed.detected_type
    if family not in interpretation_service.interpreters:
        raise HTTPException(status_code=415, detail="Byte-observed artifact family is unsupported")
    try:
        return interpretation_service.interpret(metadata, family)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Stored artifact not found") from exc


@router.get("/{artifact_id}/interpretation", response_model=InterpretationResult)
def get_interpretation(artifact_id: UUID) -> InterpretationResult:
    if artifact_service.get(artifact_id) is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    result = interpretation_service.get(artifact_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Interpretation has not been performed")
    return result


@router.post("/{artifact_id}/graph", response_model=InterpretationGraph)
def build_graph(artifact_id: UUID) -> InterpretationGraph:
    metadata = artifact_service.get(artifact_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    fastscan = fastscan_service.get(artifact_id)
    if fastscan is None:
        raise HTTPException(status_code=409, detail="FastScan must be performed first")
    interpretation = interpretation_service.get(artifact_id)
    if interpretation is None:
        raise HTTPException(status_code=409, detail="Interpretation must be performed first")
    return interpretation_graph_service.build(metadata, fastscan, interpretation)


@router.get("/{artifact_id}/graph", response_model=InterpretationGraph)
def get_graph(artifact_id: UUID) -> InterpretationGraph:
    if artifact_service.get(artifact_id) is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    graph = interpretation_graph_service.get(artifact_id)
    if graph is None:
        if interpretation_service.get(artifact_id) is None:
            raise HTTPException(status_code=409, detail="DEEP_INTERPRETATION_NOT_PERFORMED")
        raise HTTPException(status_code=500, detail="GRAPH_GENERATION_FAILED")
    return graph


@router.post("/{artifact_id}/fracture", response_model=SemanticFractureResult)
def analyze_fracture(artifact_id: UUID) -> SemanticFractureResult:
    metadata = artifact_service.get(artifact_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    fastscan = fastscan_service.get(artifact_id)
    if fastscan is None:
        raise HTTPException(status_code=409, detail="FastScan must be performed first")
    interpretation = interpretation_service.get(artifact_id)
    if interpretation is None:
        raise HTTPException(status_code=409, detail="Interpretation must be performed first")
    graph = interpretation_graph_service.get(artifact_id)
    if graph is None:
        raise HTTPException(status_code=409, detail="Interpretation Graph must be built first")
    try:
        return semantic_fracture_service.analyze(metadata, fastscan, interpretation, graph)
    except EvidenceIntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{artifact_id}/fracture", response_model=SemanticFractureResult)
def get_fracture(artifact_id: UUID) -> SemanticFractureResult:
    if artifact_service.get(artifact_id) is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    result = semantic_fracture_service.get(artifact_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Semantic Fracture analysis has not been performed")
    return result


@router.post("/{artifact_id}/dataset-record", response_model=DatasetExportResult)
def export_dataset_record(artifact_id: UUID) -> DatasetExportResult:
    metadata = artifact_service.get(artifact_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    fastscan = fastscan_service.get(artifact_id)
    if fastscan is None:
        raise HTTPException(status_code=409, detail="FastScan must be performed first")
    interpretation = interpretation_service.get(artifact_id)
    if interpretation is None:
        raise HTTPException(status_code=409, detail="Interpretation must be performed first")
    graph = interpretation_graph_service.get(artifact_id)
    if graph is None:
        raise HTTPException(status_code=409, detail="Interpretation Graph must be built first")
    fracture = semantic_fracture_service.get(artifact_id)
    if fracture is None:
        raise HTTPException(status_code=409, detail="Semantic Fracture analysis must be performed first")
    try:
        record = fracture_dataset_service.build(metadata, fastscan, interpretation, graph, fracture)
        return fracture_dataset_service.export(record)
    except DatasetEvidenceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Dataset record write failed") from exc


@router.post("/{artifact_id}/analyze", response_model=PrismOrchestrationResult)
def analyze_artifact(artifact_id: UUID) -> PrismOrchestrationResult:
    metadata = artifact_service.get(artifact_id)

    if metadata is None:
        raise HTTPException(
            status_code=404,
            detail="Artifact not found",
        )

    try:
        _analysis_results.pop(artifact_id, None)
        _reasoning_results.pop(artifact_id, None)

        stale_plan_ids = [
            plan_id
            for plan_id, plan in _lab_plans.items()
            if plan.artifact_id == artifact_id
            and plan_id not in _executed_lab_plan_ids
        ]

        for plan_id in stale_plan_ids:
            _lab_plans.pop(plan_id, None)

        result = prism_orchestration_service.analyze(metadata)
        _analysis_results[artifact_id] = result
        if artifact_id in _investigation_states:
            _investigation_states[artifact_id] = _investigation_for(artifact_id)
        return result

    except PrismOrchestrationError as exc:
        raise HTTPException(
            status_code=415,
            detail=str(exc),
        ) from exc

    except EvidenceIntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except LayaTriageError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Stored artifact not found",
        ) from exc


@router.post(
    "/{artifact_id}/lab/plan",
    response_model=PrismLabPlanningResult,
)
def plan_lab_experiments(
    artifact_id: UUID,
) -> PrismLabPlanningResult:
    artifact = artifact_service.get(artifact_id)

    if artifact is None:
        raise HTTPException(
            status_code=404,
            detail="Artifact not found",
        )

    reasoning = _reasoning_results.get(artifact_id)

    if reasoning is None:
        raise HTTPException(
            status_code=409,
            detail="Semantic reasoning must be performed before Lab planning",
        )

    try:
        result = prism_lab_planner_service.plan(reasoning, _investigation_for(artifact_id))

    except PrismLabPlannerError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    # Replace previous unexecuted plans for this artifact.
    stale_plan_ids = [
        plan_id
        for plan_id, plan in _lab_plans.items()
        if (
            plan.artifact_id == artifact_id
            and plan_id not in _executed_lab_plan_ids
        )
    ]

    for plan_id in stale_plan_ids:
        _lab_plans.pop(plan_id, None)

    for plan in result.plans:
        _lab_plans[plan.plan_id] = plan

    return result


def _execute_lab_plan_authoritatively(
    artifact_id: UUID,
    plan_id: UUID,
) -> PrismLabExperimentResult:
    artifact = artifact_service.get(artifact_id)

    if artifact is None:
        raise HTTPException(
            status_code=404,
            detail="Artifact not found",
        )

    plan = _lab_plans.get(plan_id)

    if plan is None:
        raise HTTPException(
            status_code=404,
            detail="Lab plan not found",
        )

    if plan.artifact_id != artifact_id:
        raise HTTPException(
            status_code=409,
            detail="Lab plan does not belong to this artifact",
        )

    if plan_id in _executed_lab_plan_ids:
        raise HTTPException(
            status_code=409,
            detail="Lab plan has already been executed",
        )

    if plan.status != "PLANNED":
        raise HTTPException(
            status_code=409,
            detail="Rejected Lab plans cannot be executed",
        )

    if plan.experiment_request is None:
        raise HTTPException(
            status_code=409,
            detail="Lab plan has no authorized experiment request",
        )

    if plan.candidate_kind != plan.experiment_request.experiment_kind.value:
        raise HTTPException(
            status_code=409,
            detail="Lab plan experiment kind is inconsistent",
        )

    if any(item.result.experiment_kind == plan.experiment_request.experiment_kind
           for item in _investigation_for(artifact_id).completed_experiments):
        raise HTTPException(status_code=409, detail="Lab experiment already completed")

    # Claim before execution so concurrent/replayed requests
    # cannot execute the same authorized plan twice.
    _executed_lab_plan_ids.add(plan_id)

    try:
        result = prism_lab_service.run(
            artifact,
            plan.experiment_request,
        )

        if result.artifact_id != artifact_id:
            raise HTTPException(status_code=409, detail="Lab result artifact mismatch")
        if result.experiment_kind != plan.experiment_request.experiment_kind:
            raise HTTPException(status_code=409, detail="Lab result experiment kind mismatch")

        updated_investigation = record_completed_experiment(
            _investigation_for(artifact_id), plan_id, result,
        )
        _lab_results[result.experiment_id] = result
        _investigation_states[artifact_id] = updated_investigation

        return result

    except PrismLabError as exc:
        _executed_lab_plan_ids.discard(plan_id)
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except PrismOrchestrationError as exc:
        _executed_lab_plan_ids.discard(plan_id)
        raise HTTPException(
            status_code=415,
            detail=str(exc),
        ) from exc

    except EvidenceIntegrityError as exc:
        _executed_lab_plan_ids.discard(plan_id)
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except FileNotFoundError as exc:
        _executed_lab_plan_ids.discard(plan_id)
        raise HTTPException(
            status_code=404,
            detail="Stored artifact not found",
        ) from exc


    except Exception:
        _executed_lab_plan_ids.discard(plan_id)
        raise


@router.post(
    "/{artifact_id}/lab/plans/{plan_id}/execute",
    response_model=PrismLabExperimentResult,
)
def execute_lab_plan(
    artifact_id: UUID,
    plan_id: UUID,
) -> PrismLabExperimentResult:
    return _execute_lab_plan_authoritatively(artifact_id, plan_id)


@router.post("/{artifact_id}/reason", response_model=SemanticReasoningResult)
def reason_artifact(artifact_id: UUID) -> SemanticReasoningResult:
    artifact = artifact_service.get(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    analysis = _analysis_results.get(artifact_id)
    if analysis is None:
        raise HTTPException(status_code=409, detail="Analyze the artifact before semantic reasoning")
    fastscan = fastscan_service.get(artifact_id)
    if fastscan is None:
        raise HTTPException(status_code=409, detail="FastScan evidence is unavailable")
    investigation = _investigation_for(artifact_id)

    # Read-only containment history.
    # Never use this value to derive verified_state.
    containment = quarantine_service.for_artifact(artifact_id)

    lab_deep_completed = any(
        item.result.status == "COMPLETED"
        and item.result.deterministic
        and item.result.deep_scan_performed
        for item in investigation.completed_experiments
    )

    # Keep the historical orchestration result untouched while allowing
    # semantic reasoning to consume deterministic deep evidence generated
    # later by PRISM Lab.
    effective_deep = (
        analysis.deep_scan_performed
        or lab_deep_completed
    )

    try:
        result = semantic_reasoning_service.reason(
            artifact,
            fastscan,
            analysis,
            interpretation_service.get(artifact_id) if effective_deep else None,
            interpretation_graph_service.get(artifact_id) if effective_deep else None,
            semantic_fracture_service.get(artifact_id) if effective_deep else None,
            investigation=investigation,
            containment=containment,
        )

        # The planner consumes this server-side result.
        # The browser never supplies authoritative reasoning back to PRISM.
        stale_plan_ids = [
            plan_id for plan_id, plan in _lab_plans.items()
            if plan.artifact_id == artifact_id
            and plan_id not in _executed_lab_plan_ids
        ]
        for plan_id in stale_plan_ids:
            _lab_plans.pop(plan_id, None)
        _reasoning_results[artifact_id] = result

        return result
    except SemanticReasoningError as exc:
        raise HTTPException(status_code=409 if "evidence" in str(exc).lower() else 502,
                            detail=str(exc)) from exc
    except (RagIndexError, RagModelError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{artifact_id}/investigation", response_model=ArtifactInvestigationState)
def get_investigation(artifact_id: UUID) -> ArtifactInvestigationState:
    if artifact_service.get(artifact_id) is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return _investigation_for(artifact_id)



def _reason_for_autonomous(
    artifact_id: UUID,
) -> SemanticReasoningResult:
    """Reuse the normal server-side reasoning path."""

    return reason_artifact(artifact_id)


def _plan_for_autonomous(
    artifact_id: UUID,
    reasoning: SemanticReasoningResult,
) -> PrismLabPlanningResult:
    """Reuse normal planning without accepting client-supplied reasoning."""

    stored = _reasoning_results.get(artifact_id)

    if stored is not reasoning:
        raise HTTPException(
            status_code=409,
            detail="Autonomous reasoning is not the current server-side reasoning result",
        )

    return plan_lab_experiments(artifact_id)


def _evidence_for_autonomous(
    artifact_id: UUID,
):
    """
    Build fresh deterministic evidence, then pass only that
    evidence through the read-only Evidence Agent.
    """
    artifact = artifact_service.get(
        artifact_id
    )

    if artifact is None:
        raise HTTPException(
            status_code=404,
            detail="Artifact not found",
        )

    analysis = _analysis_results.get(
        artifact_id
    )

    if analysis is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Analyze the artifact before "
                "autonomous investigation"
            ),
        )

    fastscan = fastscan_service.get(
        artifact_id
    )

    if fastscan is None:
        raise HTTPException(
            status_code=409,
            detail="FastScan evidence is unavailable",
        )

    deep = analysis.deep_scan_performed

    try:
        bundle = (
            semantic_reasoning_service
            .build_evidence(
                artifact,
                fastscan,
                analysis,
                (
                    interpretation_service.get(
                        artifact_id
                    )
                    if deep
                    else None
                ),
                (
                    interpretation_graph_service.get(
                        artifact_id
                    )
                    if deep
                    else None
                ),
                (
                    semantic_fracture_service.get(
                        artifact_id
                    )
                    if deep
                    else None
                ),
                investigation=(
                    _investigation_for(
                        artifact_id
                    )
                ),
            )
        )

        return evidence_agent_service.evaluate(bundle)

    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


def _hypothesize_for_autonomous(
    evidence,
):
    try:
        return hypothesis_agent_service.generate(
            evidence
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


def _propose_for_autonomous(
    evidence,
    hypothesis,
):
    try:
        return experiment_agent_service.propose(
            evidence,
            hypothesis,
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


def _plan_agents_for_autonomous(
    evidence,
    experiment_agent,
):
    try:
        result = (
            prism_lab_planner_service
            .plan_agent_proposals(
                evidence,
                experiment_agent,
                _investigation_for(
                    evidence.artifact_id
                ),
            )
        )

    except PrismLabPlannerError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    # Same stale-plan semantics as the legacy planning API.
    stale_plan_ids = [
        plan_id
        for plan_id, plan
        in _lab_plans.items()
        if (
            plan.artifact_id
            == evidence.artifact_id
            and plan_id
            not in _executed_lab_plan_ids
        )
    ]

    for plan_id in stale_plan_ids:
        _lab_plans.pop(
            plan_id,
            None,
        )

    for plan in result.plans:
        _lab_plans[
            plan.plan_id
        ] = plan

    return result


def _validate_for_autonomous(
    post_evidence,
    hypothesis,
    experiment_result,
):
    try:
        return validation_agent_service.validate(
            post_evidence,
            hypothesis,
            experiment_result,
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


autonomous_investigation_service = AutonomousInvestigationService(
    evidence=_evidence_for_autonomous,
    hypothesize=_hypothesize_for_autonomous,
    propose=_propose_for_autonomous,
    plan_agents=_plan_agents_for_autonomous,
    execute=_execute_lab_plan_authoritatively,
    validate=_validate_for_autonomous,
    get_investigation=_investigation_for,
    controlled_error_types=(HTTPException,),
)


@router.post(
    "/{artifact_id}/investigate",
    response_model=AutonomousInvestigationResult,
)
def investigate_artifact(
    artifact_id: UUID,
) -> AutonomousInvestigationResult:
    """Run one bounded autonomous PRISM Lab investigation."""

    artifact = artifact_service.get(artifact_id)

    if artifact is None:
        raise HTTPException(
            status_code=404,
            detail="Artifact not found",
        )

    if _analysis_results.get(artifact_id) is None:
        raise HTTPException(
            status_code=409,
            detail="Analyze the artifact before autonomous investigation",
        )

    if fastscan_service.get(artifact_id) is None:
        raise HTTPException(
            status_code=409,
            detail="FastScan evidence is unavailable",
        )

    # Atomic in-process check + claim.
    with _autonomous_investigation_guard:
        if artifact_id in _autonomous_investigations_running:
            raise HTTPException(
                status_code=409,
                detail="Autonomous investigation is already running for this artifact",
            )

        _autonomous_investigations_running.add(artifact_id)

    try:
        return autonomous_investigation_service.run(artifact_id)

    finally:
        # Always release: normal completion, bounded stop,
        # controlled failure, or unexpected exception.
        with _autonomous_investigation_guard:
            _autonomous_investigations_running.discard(artifact_id)
