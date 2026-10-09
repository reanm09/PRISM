from fastapi import APIRouter, HTTPException

from app.api.artifacts import fracture_dataset_service
from app.schemas.fracture_dataset import DatasetRecord
from app.services.fracture_dataset_service import InvalidSampleIdError


router = APIRouter(prefix="/api/dataset", tags=["dataset"])


@router.get("/records/{sample_id}", response_model=DatasetRecord)
def get_dataset_record(sample_id: str) -> DatasetRecord:
    try:
        return fracture_dataset_service.read(sample_id)
    except InvalidSampleIdError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dataset record not found") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Dataset record read failed") from exc
