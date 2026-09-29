import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_current_user
from app.rag.ingestion.pipeline import IngestionPipeline
from app.rag.schemas.chat import (
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
)
from app.rag.schemas.rag import RAGQueryRequest, RAGQueryResponse
from app.rag.services.chat_service import ChatService
from app.rag.services.rag_service import RAGService, default_rag_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["rag"])
chat_service = ChatService()


@router.post("/query", response_model=RAGQueryResponse)
async def query_rag(
    request: RAGQueryRequest,
    current_user: Dict[str, str] = Depends(get_current_user),
) -> RAGQueryResponse:
    """
    Execute an evidence-grounded semantic retrieval and generation query.
    Requires an authenticated Supabase user.
    """
    if not request.question and not request.artifact_evidence:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'question' or 'artifact_evidence' must be provided.",
        )

    try:
        response = default_rag_service.answer(
            request=request,
            user_id=current_user["id"],
        )
        return response
    except Exception as exc:
        logger.error("RAG query failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG query execution failed: {str(exc)}",
        ) from exc


@router.post("/ingest")
async def trigger_ingestion(
    current_user: Dict[str, str] = Depends(get_current_user),
) -> dict:
    """
    Programmatically run the PRISM knowledge ingestion pipeline.
    Embeds mock/seed documents into Supabase pgvector with deduplication.
    """
    try:
        pipeline = IngestionPipeline()
        result = pipeline.run()
        return result
    except Exception as exc:
        logger.error("Ingestion failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(exc)}",
        ) from exc


@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_chat_sessions(
    current_user: Dict[str, str] = Depends(get_current_user),
) -> List[ChatSessionResponse]:
    """List all chat sessions for the authenticated user."""
    return chat_service.list_sessions(user_id=current_user["id"])


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    payload: ChatSessionCreate,
    current_user: Dict[str, str] = Depends(get_current_user),
) -> ChatSessionResponse:
    """Create a new chat session for the authenticated user."""
    return chat_service.create_session(
        user_id=current_user["id"],
        title=payload.title,
    )


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
async def get_session_messages(
    session_id: str,
    current_user: Dict[str, str] = Depends(get_current_user),
) -> List[ChatMessageResponse]:
    """Retrieve message history for a specific session."""
    return chat_service.get_messages(session_id=session_id, user_id=current_user["id"])
