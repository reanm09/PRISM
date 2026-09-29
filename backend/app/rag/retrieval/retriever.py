import logging
import time
from typing import Any, Dict, List, Optional

from app.rag.embeddings.service import EmbeddingService, default_embedding_service
from app.rag.schemas.retrieval import RetrievalQuery, RetrievalResult
from app.rag.vector_store.base import VectorStore
from app.rag.vector_store.supabase_store import SupabaseVectorStore

logger = logging.getLogger(__name__)


class SemanticRetriever:
    """
    Coordinates semantic vector retrieval:
    User Query -> Query Embedding (BGE-M3) -> Supabase pgvector search -> Filtered Chunks.
    """

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        vector_store: Optional[VectorStore] = None,
    ):
        self.embedding_service = embedding_service or default_embedding_service
        self.vector_store = vector_store or SupabaseVectorStore()

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        match_threshold: float = 0.0,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievalResult]:
        clean_query = query.strip()
        if not clean_query:
            return []

        start_time = time.perf_counter()

        # Step 1: Embed query into 1024-dim vector using BGE-M3
        query_embedding = self.embedding_service.embed_text(clean_query)

        # Step 2: Query vector store
        results = self.vector_store.similarity_search(
            query_embedding=query_embedding,
            top_k=top_k,
            match_threshold=match_threshold,
            filters=filters,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Retrieved %d chunks for query '%s' in %.2f ms",
            len(results),
            clean_query[:50],
            elapsed_ms,
        )

        return results
