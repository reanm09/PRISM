from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.rag.schemas.document import DocumentChunk
from app.rag.schemas.retrieval import RetrievalResult


class VectorStore(ABC):
    @abstractmethod
    def add_documents(
        self,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]],
    ) -> List[str]:
        """Insert or upsert document chunks along with their vector embeddings."""
        pass

    @abstractmethod
    def similarity_search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        match_threshold: float = 0.0,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievalResult]:
        """Perform semantic similarity search against stored vector embeddings."""
        pass

    @abstractmethod
    def delete(self, chunk_ids: List[str]) -> bool:
        """Delete document chunks by ID."""
        pass

    @abstractmethod
    def get(self, chunk_id: str) -> Optional[RetrievalResult]:
        """Fetch a specific chunk by ID."""
        pass
