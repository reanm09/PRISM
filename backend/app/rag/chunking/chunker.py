import hashlib
import re
from typing import List, Optional
import uuid

from app.rag.chunking.base import Chunker
from app.rag.schemas.document import ChunkMetadata, Document, DocumentChunk


class StandardDocumentChunker(Chunker):
    """
    Standard paragraph- and sentence-aware chunker.
    Creates deterministic chunk hashes for idempotent deduplication.
    """

    def __init__(self, max_chunk_size: int = 500, chunk_overlap: int = 50):
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, document: Document) -> List[DocumentChunk]:
        content = document.content.strip()
        doc_id = document.id or str(uuid.uuid5(uuid.NAMESPACE_DNS, document.title))

        category_parts = [p.strip() for p in document.category.split("/") if p.strip()]
        primary_category = category_parts[0] if category_parts else "general"
        topic = category_parts[1] if len(category_parts) > 1 else document.metadata.get("topic", "general")

        # For small documents or single paragraphs that fit in max_chunk_size
        if len(content) <= self.max_chunk_size:
            chunk_hash = self._generate_chunk_hash(document.title, 0, content)
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_id}::0::{chunk_hash}"))
            
            metadata = ChunkMetadata(
                document_type=document.metadata.get("document_type", "knowledge"),
                category=primary_category,
                topic=topic,
                source=document.metadata.get("source", "mock_seed"),
                document_id=doc_id,
                chunk_index=0,
                chunk_hash=chunk_hash,
                extra=document.metadata,
            )
            return [
                DocumentChunk(
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    title=document.title,
                    category=document.category,
                    content=content,
                    metadata=metadata,
                )
            ]

        # Multi-chunk splitting on paragraphs / sentences for larger documents
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
        raw_chunks: List[str] = []
        current_chunk = ""

        for para in paragraphs:
            if not current_chunk:
                current_chunk = para
            elif len(current_chunk) + len(para) + 1 <= self.max_chunk_size:
                current_chunk += "\n\n" + para
            else:
                raw_chunks.append(current_chunk)
                current_chunk = para

        if current_chunk:
            raw_chunks.append(current_chunk)

        result_chunks: List[DocumentChunk] = []
        for idx, text in enumerate(raw_chunks):
            chunk_hash = self._generate_chunk_hash(document.title, idx, text)
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_id}::{idx}::{chunk_hash}"))
            metadata = ChunkMetadata(
                document_type=document.metadata.get("document_type", "knowledge"),
                category=primary_category,
                topic=topic,
                source=document.metadata.get("source", "mock_seed"),
                document_id=doc_id,
                chunk_index=idx,
                chunk_hash=chunk_hash,
                extra=document.metadata,
            )
            result_chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    title=document.title,
                    category=document.category,
                    content=text,
                    metadata=metadata,
                )
            )

        return result_chunks

    @staticmethod
    def _generate_chunk_hash(title: str, chunk_index: int, content: str) -> str:
        raw = f"{title}::{chunk_index}::{content.strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
