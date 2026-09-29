import logging
import time
from typing import List, Optional

from app.rag.embeddings.base import EmbeddingProvider
from app.rag.embeddings.bge_provider import BGEEmbeddingProvider

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Embedding service orchestrating text and document embeddings.
    Accepts any EmbeddingProvider implementation (default: BGEEmbeddingProvider).
    """

    def __init__(self, provider: Optional[EmbeddingProvider] = None):
        self._provider = provider or BGEEmbeddingProvider()

    @property
    def provider(self) -> EmbeddingProvider:
        return self._provider

    @property
    def dimension(self) -> int:
        return self._provider.dimension

    def embed_text(self, text: str) -> List[float]:
        start = time.perf_counter()
        embedding = self._provider.embed_text(text)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.debug("Embedded text (length %d) into %d-dim in %.2f ms", len(text), len(embedding), elapsed_ms)
        return embedding

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        start = time.perf_counter()
        embeddings = self._provider.embed_documents(texts)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("Embedded %d documents into %d-dim in %.2f ms", len(texts), self.dimension, elapsed_ms)
        return embeddings


# Singleton instance
default_embedding_service = EmbeddingService()
