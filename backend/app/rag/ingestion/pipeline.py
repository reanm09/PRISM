import logging
import time
from typing import List, Optional

from app.rag.chunking.base import Chunker
from app.rag.chunking.chunker import StandardDocumentChunker
from app.rag.embeddings.service import EmbeddingService, default_embedding_service
from app.rag.ingestion.loader import CompositeDocumentLoader, DocumentLoader
from app.rag.schemas.document import DocumentChunk
from app.rag.vector_store.base import VectorStore
from app.rag.vector_store.supabase_store import SupabaseVectorStore

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """
    Orchestrates the ingestion lifecycle:
    Documents -> Chunker -> Normalization -> BGE-M3 Embeddings -> Supabase Vector Store.
    Ensures idempotency through deterministic chunk hashing.
    Supports both mock seed documents and real PRISM knowledge documents.
    """

    def __init__(
        self,
        loader: Optional[DocumentLoader] = None,
        chunker: Optional[Chunker] = None,
        embedding_service: Optional[EmbeddingService] = None,
        vector_store: Optional[VectorStore] = None,
    ):
        self.loader = loader or CompositeDocumentLoader(include_mock=True, include_real=True)
        self.chunker = chunker or StandardDocumentChunker()
        self.embedding_service = embedding_service or default_embedding_service
        self.vector_store = vector_store or SupabaseVectorStore()

    def run(self) -> dict:
        start_time = time.perf_counter()
        logger.info("=== Ingestion pipeline started ===")

        # 1. Load documents
        documents = self.loader.load()
        doc_count = len(documents)
        logger.info("Loaded %d documents", doc_count)

        if not documents:
            logger.warning("No documents loaded. Ingestion terminating early.")
            return {"status": "empty", "documents": 0, "chunks": 0}

        # 2. Chunk documents
        all_chunks: List[DocumentChunk] = []
        for doc in documents:
            chunks = self.chunker.chunk(doc)
            all_chunks.extend(chunks)

        chunk_count = len(all_chunks)
        logger.info("Chunking completed: %d total chunks created", chunk_count)

        # 3. Generate BGE-M3 embeddings
        emb_start = time.perf_counter()
        texts_to_embed = [f"{c.title}\n{c.content}" for c in all_chunks]
        embeddings = self.embedding_service.embed_documents(texts_to_embed)
        emb_duration_ms = (time.perf_counter() - emb_start) * 1000
        logger.info("Generated %d embeddings (%d-dim) in %.2f ms", len(embeddings), self.embedding_service.dimension, emb_duration_ms)

        # 4. Insert / upsert into Supabase pgvector
        store_start = time.perf_counter()
        inserted_ids = self.vector_store.add_documents(all_chunks, embeddings)
        store_duration_ms = (time.perf_counter() - store_start) * 1000
        logger.info("Stored %d records into vector store in %.2f ms", len(inserted_ids), store_duration_ms)

        total_duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info("=== Ingestion completed successfully in %.2f ms ===", total_duration_ms)

        return {
            "status": "success",
            "document_count": doc_count,
            "chunk_count": chunk_count,
            "inserted_count": len(inserted_ids),
            "dimension": self.embedding_service.dimension,
            "embedding_time_ms": round(emb_duration_ms, 2),
            "total_time_ms": round(total_duration_ms, 2),
            "records": [
                {"title": c.title, "chunk_id": c.chunk_id, "category": c.category}
                for c in all_chunks
            ],
        }
