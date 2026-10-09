from fastapi import APIRouter, HTTPException

from app.schemas.rag import RagQueryRequest, RagQueryResult
from app.services.rag.models import RagModelError
from app.services.rag.service import RagIndexError
from app.services.rag.runtime import rag_service


router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.post("/query", response_model=RagQueryResult)
def query_rag(request: RagQueryRequest) -> RagQueryResult:
    try:
        return rag_service.query(request.query, request.top_k)
    except RagModelError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RagIndexError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
