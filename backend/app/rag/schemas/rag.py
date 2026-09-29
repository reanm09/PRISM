from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SourceCitation(BaseModel):
    chunk_id: str
    title: str
    category: str
    similarity: float
    snippet: Optional[str] = None


class DebugInfo(BaseModel):
    query_processed: str
    embedding_dimension: int
    retrieval_latency_ms: float
    generation_latency_ms: float
    retrieved_count: int
    top_scores: List[Dict[str, Any]]
    context_length: int
    prompt_sent: Optional[str] = None


class ArtifactEvidenceInput(BaseModel):
    artifact_id: Optional[str] = None
    artifact_family: str
    fracture_type: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)


class RAGQueryRequest(BaseModel):
    question: Optional[str] = None
    artifact_evidence: Optional[ArtifactEvidenceInput] = None
    session_id: Optional[str] = None
    top_k: Optional[int] = None
    match_threshold: Optional[float] = None
    include_debug: bool = False


class RAGQueryResponse(BaseModel):
    answer: str
    sources: List[SourceCitation]
    debug: Optional[DebugInfo] = None
