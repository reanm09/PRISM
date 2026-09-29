from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    document_type: str = "knowledge"
    category: str = "general"
    topic: str = "general"
    source: str = "mock_seed"
    document_id: str
    chunk_index: int = 0
    chunk_hash: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class Document(BaseModel):
    id: Optional[str] = None
    title: str
    category: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    category: str
    content: str
    metadata: ChunkMetadata
