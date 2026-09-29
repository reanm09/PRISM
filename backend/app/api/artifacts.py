from uuid import UUID

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.core.config import settings
from app.schemas.artifact import ArtifactMetadata
from app.schemas.fastscan import FastScanResult
from app.schemas.interpretation import InterpretationResult
from app.schemas.interpretation_graph import InterpretationGraph
from app.services.artifact_service import (
    ArtifactService,
    ArtifactTooLargeError,
    EmptyArtifactError,
)
from app.services.fastscan_service import FastScanService
from app.services.interpretation_service import InterpretationService
from app.services.interpretation_graph_service import InterpretationGraphService


router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])
artifact_service = ArtifactService(settings)
fastscan_service = FastScanService(settings.artifact_storage)
interpretation_service = InterpretationService(settings.artifact_storage, settings.max_upload_bytes)
interpretation_graph_service = InterpretationGraphService()


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
        raise HTTPException(status_code=404, detail="Graph has not been built")
    return graph
