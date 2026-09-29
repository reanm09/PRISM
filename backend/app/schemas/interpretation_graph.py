from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GraphNode(BaseModel):
    id: str
    type: Literal["ARTIFACT", "CLAIM", "OBSERVED_IDENTITY", "INTERPRETER", "OBSERVATION", "SIGNAL"]
    label: str
    data: dict[str, Any]


class GraphEdge(BaseModel):
    source: str
    target: str
    type: Literal["HAS_CLAIM", "FASTSCAN_OBSERVED_AS", "ANALYZED_BY", "INTERPRETED_AS", "OBSERVED", "HAS_SIGNAL"]


class GraphSummary(BaseModel):
    node_count: int
    edge_count: int
    interpreter_count: int
    disagreement_count: int


class InterpretationGraph(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: UUID
    sha256: str
    artifact_family: Literal["PDF", "ZIP", "PNG"]
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    summary: GraphSummary
    status: Literal["COMPLETE"] = "COMPLETE"
