import logging
import time
from typing import Optional

from app.rag.config.rag_config import rag_settings
from app.rag.context.builder import ContextBuilder
from app.rag.embeddings.service import EmbeddingService, default_embedding_service
from app.rag.llm.base import LLMProvider
from app.rag.llm.qwen_provider import QwenProvider
from app.rag.retrieval.retriever import SemanticRetriever
from app.rag.schemas.rag import (
    ArtifactEvidenceInput,
    DebugInfo,
    RAGQueryRequest,
    RAGQueryResponse,
    SourceCitation,
)
from app.rag.services.chat_service import ChatService
from app.rag.vector_store.supabase_store import SupabaseVectorStore

logger = logging.getLogger(__name__)


class RAGService:
    """
    Main orchestration service for PRISM Lab RAG:
    User Question (or Structured Evidence)
    -> Query Builder
    -> BGE-M3 1024-dim Query Embedding
    -> Supabase pgvector Similarity Search
    -> Context Builder
    -> Qwen3-4B Grounded Generation
    -> Grounded Answer & Source Citations
    """

    def __init__(
        self,
        retriever: Optional[SemanticRetriever] = None,
        context_builder: Optional[ContextBuilder] = None,
        llm_provider: Optional[LLMProvider] = None,
        chat_service: Optional[ChatService] = None,
    ):
        self.retriever = retriever or SemanticRetriever()
        self.context_builder = context_builder or ContextBuilder()
        self.llm = llm_provider or QwenProvider()
        self.chat_service = chat_service or ChatService()

    def _build_query_from_evidence(self, evidence_input: ArtifactEvidenceInput) -> str:
        """
        Translates structured PRISM artifact evidence into an optimal vector retrieval query.
        Supports future PRISM integration requirements.
        """
        parts = [f"Artifact Family: {evidence_input.artifact_family}"]
        if evidence_input.fracture_type:
            parts.append(f"Fracture Type: {evidence_input.fracture_type}")

        for k, v in evidence_input.evidence.items():
            if isinstance(v, bool) and v:
                parts.append(f"{k.replace('_', ' ')}")
            elif isinstance(v, (int, str)):
                parts.append(f"{k}: {v}")

        return " ".join(parts) + " parser behavior interpretation"

    def answer(
        self,
        request: RAGQueryRequest,
        user_id: Optional[str] = None,
    ) -> RAGQueryResponse:
        # Determine actual text query
        if request.question and request.question.strip():
            raw_query = request.question.strip()
        elif request.artifact_evidence:
            raw_query = self._build_query_from_evidence(request.artifact_evidence)
        else:
            return RAGQueryResponse(
                answer="No query question or artifact evidence provided.",
                sources=[],
            )

        top_k = request.top_k or rag_settings.vector_top_k
        match_threshold = (
            request.match_threshold
            if request.match_threshold is not None
            else rag_settings.vector_match_threshold
        )

        logger.info("Processing RAG query: '%s' (top_k=%d, threshold=%.2f)", raw_query[:60], top_k, match_threshold)

        # 1. Retrieval
        retrieval_start = time.perf_counter()
        retrieval_results = self.retriever.retrieve(
            query=raw_query,
            top_k=top_k,
            match_threshold=match_threshold,
        )
        retrieval_ms = (time.perf_counter() - retrieval_start) * 1000

        # 2. Context Building
        context_str, citations = self.context_builder.build_context(retrieval_results)
        prompt_text = self.context_builder.format_prompt(raw_query, context_str)

        # 3. Qwen Generation
        gen_start = time.perf_counter()
        generated_answer = self.llm.generate(
            prompt=prompt_text,
            system_prompt=self.context_builder.system_prompt,
        )
        gen_ms = (time.perf_counter() - gen_start) * 1000

        # 4. Optional Chat Persistence
        if request.session_id and user_id:
            try:
                # Store user message
                self.chat_service.add_message(
                    session_id=request.session_id,
                    user_id=user_id,
                    role="user",
                    content=raw_query,
                )
                # Store assistant response with citations
                meta = {
                    "sources": [c.model_dump() for c in citations],
                    "retrieval_latency_ms": round(retrieval_ms, 2),
                    "generation_latency_ms": round(gen_ms, 2),
                }
                self.chat_service.add_message(
                    session_id=request.session_id,
                    user_id=user_id,
                    role="assistant",
                    content=generated_answer,
                    retrieval_metadata=meta,
                )
            except Exception as exc:
                logger.warning("Failed to persist chat message: %s", exc)

        # 5. Build Debug Info if requested
        debug_info = None
        if request.include_debug:
            debug_info = DebugInfo(
                query_processed=raw_query,
                embedding_dimension=self.retriever.embedding_service.dimension,
                retrieval_latency_ms=round(retrieval_ms, 2),
                generation_latency_ms=round(gen_ms, 2),
                retrieved_count=len(retrieval_results),
                top_scores=[
                    {"title": r.title, "similarity": round(r.similarity, 4), "category": r.category}
                    for r in retrieval_results
                ],
                context_length=len(context_str),
                prompt_sent=prompt_text if request.include_debug else None,
            )

        return RAGQueryResponse(
            answer=generated_answer,
            sources=citations,
            debug=debug_info,
        )


# Singleton instance
default_rag_service = RAGService()
