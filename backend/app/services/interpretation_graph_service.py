import re
from uuid import UUID

from app.schemas.artifact import ArtifactMetadata
from app.schemas.fastscan import FastScanResult
from app.schemas.interpretation import InterpretationResult
from app.schemas.interpretation_graph import GraphEdge, GraphNode, GraphSummary, InterpretationGraph


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", value.lower()).strip("-") or "none"


class InterpretationGraphService:
    def __init__(self):
        self._graphs: dict[UUID, InterpretationGraph] = {}

    def get(self, artifact_id: UUID) -> InterpretationGraph | None:
        return self._graphs.get(artifact_id)

    def build(
        self,
        artifact: ArtifactMetadata,
        fastscan: FastScanResult,
        interpretation: InterpretationResult,
    ) -> InterpretationGraph:
        artifact_id = str(artifact.artifact_id)
        root_id = f"artifact:{artifact_id}"
        claim_id = f"claim:{artifact_id}:extension"
        nodes = [GraphNode(
            id=root_id, type="ARTIFACT", label=artifact.original_name,
            data={
                "artifact_id": artifact_id,
                "sha256": artifact.sha256,
                "size_bytes": artifact.size_bytes,
            },
        ), GraphNode(
            id=claim_id, type="CLAIM", label=artifact.claimed_extension or "(none)",
            data={"claim_type": "FILE_EXTENSION", "value": artifact.claimed_extension},
        )]
        edges = [GraphEdge(source=root_id, target=claim_id, type="HAS_CLAIM")]
        identities: set[str] = set()

        def add_identity(identity: str, source: str, mime: str | None = None, description: str | None = None) -> str:
            node_id = f"identity:{artifact_id}:{_key(identity)}"
            if node_id not in identities:
                data = {"source": source}
                if mime is not None:
                    data["mime"] = mime
                if description is not None:
                    data["magic_description"] = description
                nodes.append(GraphNode(id=node_id, type="OBSERVED_IDENTITY", label=identity, data=data))
                identities.add(node_id)
            return node_id

        observed = fastscan.observed
        fastscan_identity_id = add_identity(
            observed.detected_type, "FASTSCAN", observed.detected_mime, observed.magic_description,
        )
        edges.append(GraphEdge(source=root_id, target=fastscan_identity_id, type="FASTSCAN_OBSERVED_AS"))

        for result in interpretation.interpreters:
            interpreter_id = f"interpreter:{artifact_id}:{_key(result.interpreter)}"
            nodes.append(GraphNode(
                id=interpreter_id, type="INTERPRETER", label=result.interpreter,
                data={
                    "version": result.interpreter_version,
                    "recognized": result.recognized,
                    "valid": result.valid,
                    "warnings": result.warnings,
                    "errors": result.errors,
                },
            ))
            edges.append(GraphEdge(source=root_id, target=interpreter_id, type="ANALYZED_BY"))
            if result.identity is not None:
                identity_id = add_identity(result.identity, "INTERPRETER")
                edges.append(GraphEdge(source=interpreter_id, target=identity_id, type="INTERPRETED_AS"))
            for key, value in result.observations.model_dump(exclude_none=True).items():
                observation_id = f"observation:{artifact_id}:{_key(result.interpreter)}:{_key(key)}"
                nodes.append(GraphNode(
                    id=observation_id, type="OBSERVATION", label=f"{key}: {str(value).lower() if isinstance(value, bool) else value}",
                    data={"key": key, "value": value, "interpreter": result.interpreter},
                ))
                edges.append(GraphEdge(source=interpreter_id, target=observation_id, type="OBSERVED"))

        for source, signals in (("fastscan", fastscan.signals), ("interpretation", interpretation.signals)):
            for signal in signals:
                signal_id = f"signal:{artifact_id}:{source}:{_key(signal.code)}"
                nodes.append(GraphNode(
                    id=signal_id, type="SIGNAL", label=signal.code,
                    data={"source": source.upper(), **signal.model_dump()},
                ))
                edges.append(GraphEdge(source=root_id, target=signal_id, type="HAS_SIGNAL"))

        graph = InterpretationGraph(
            artifact_id=artifact.artifact_id,
            sha256=artifact.sha256,
            artifact_family=interpretation.artifact_family,
            nodes=nodes,
            edges=edges,
            summary=GraphSummary(
                node_count=len(nodes),
                edge_count=len(edges),
                interpreter_count=len(interpretation.interpreters),
                disagreement_count=len(interpretation.signals),
            ),
        )
        self._graphs[artifact.artifact_id] = graph
        return graph
