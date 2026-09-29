from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class RetrievalFilter(BaseModel):
    category: Optional[str] = None
    topic: Optional[str] = None
    source: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetrievalQuery(BaseModel):
    query: str
    top_k: int = 5
    match_threshold: float = 0.0
    filters: Optional[RetrievalFilter] = None


class RetrievalResult(BaseModel):
    chunk_id: str
    title: str
    content: str
    category: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    similarity: float
