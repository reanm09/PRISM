from typing import Any

from pydantic import BaseModel, Field


class KnowledgeDocument(BaseModel):
    source_id: str = Field(min_length=1, max_length=256)
    source: str = Field(min_length=1, max_length=1024)
    title: str = Field(min_length=1, max_length=256)
    text: str = Field(min_length=1, max_length=1_000_000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagSource(BaseModel):
    chunk_id: str
    source_id: str
    source: str
    title: str
    text: str
    score: float
    metadata: dict[str, Any]


class RagQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=10)


class RagQueryResult(BaseModel):
    query: str
    answer: str
    sources: list[RagSource]
