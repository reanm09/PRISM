from uuid import UUID

from app.interpreters.zip.name_report import comparable_zip_names
from app.schemas.artifact import ArtifactMetadata
from app.schemas.fastscan import FastScanResult
from app.schemas.interpretation import InterpretationResult, InterpreterResult
from app.schemas.interpretation_graph import InterpretationGraph
from app.schemas.semantic_fracture import (
    ContextSignal,
    FractureClassification,
    FractureRecord,
    FractureSummary,
    SemanticFractureResult,
)


class EvidenceIntegrityError(ValueError):
    pass


RULES = (
    ("IDENTITY_DISAGREEMENT", None, "identity", FractureClassification.IDENTITY_DISAGREEMENT, "HIGH",
     "Independent interpreters recognized different identities for the same artifact."),
    ("VALIDITY_DISAGREEMENT", None, "valid", FractureClassification.VALIDITY_DISAGREEMENT, "HIGH",
     "Independent consumers disagreed on whether the artifact was processable."),
    ("PAGE_COUNT_DISAGREEMENT", "PDF", "page_count", FractureClassification.STRUCTURAL_DISAGREEMENT, "MEDIUM",
     "Independent PDF interpreters reported different page counts for the same artifact."),
    ("ENCRYPTION_STATE_DISAGREEMENT", "PDF", "encrypted", FractureClassification.BOUNDARY_DISAGREEMENT, "HIGH",
     "Independent PDF interpreters reported different encryption states."),
    ("ZIP_ENTRY_COUNT_DISAGREEMENT", "ZIP", "entry_count", FractureClassification.STRUCTURAL_DISAGREEMENT, "MEDIUM",
     "Independent ZIP consumers reported different archive entry counts."),
    ("ZIP_UNCOMPRESSED_SIZE_DISAGREEMENT", "ZIP", "total_uncompressed_size", FractureClassification.BOUNDARY_DISAGREEMENT, "MEDIUM",
     "Independent ZIP consumers reported different uncompressed content sizes."),
    ("ZIP_ENTRY_NAME_SET_DISAGREEMENT", "ZIP", "entry_name_set", FractureClassification.STRUCTURAL_DISAGREEMENT, "MEDIUM",
     "Independent ZIP consumers reported different logical entry-name sets."),
    ("ZIP_DUPLICATE_NAME_DISAGREEMENT", "ZIP", "duplicate_entry_names", FractureClassification.STRUCTURAL_DISAGREEMENT, "MEDIUM",
     "Independent ZIP consumers reported different duplicate logical entry names."),
    ("IMAGE_DIMENSION_DISAGREEMENT", "PNG", "image_dimensions", FractureClassification.STRUCTURAL_DISAGREEMENT, "MEDIUM",
     "Independent PNG consumers reported different image dimensions."),
)


def _values(left: InterpreterResult, right: InterpreterResult, field: str) -> tuple[object, object]:
    if field in ("identity", "valid"):
        return getattr(left, field), getattr(right, field)
    if field == "image_dimensions":
        a, b = left.observations, right.observations
        if None in (a.width, a.height, b.width, b.height):
            return None, None
        return f"{a.width}x{a.height}", f"{b.width}x{b.height}"
    if field == "entry_name_set":
        a, b = left.observations.entry_names, right.observations.entry_names
        return (sorted(set(a)) if a is not None else None,
                sorted(set(b)) if b is not None else None)
    return getattr(left.observations, field), getattr(right.observations, field)


def _graph_refs(graph: InterpretationGraph, names: list[str], field: str) -> list[str]:
    if field == "image_dimensions":
        observation_keys = {"width", "height"}
    elif field == "entry_name_set":
        observation_keys = {"entry_names"}
    elif field in ("identity", "valid"):
        observation_keys = set()
    else:
        observation_keys = {field}
    references = []
    for node in graph.nodes:
        if node.type == "INTERPRETER" and field in ("identity", "valid") and node.label in names:
            references.append(node.id)
        elif node.type == "OBSERVATION" and node.data.get("interpreter") in names and node.data.get("key") in observation_keys:
            references.append(node.id)
    return references


class SemanticFractureService:
    def __init__(self):
        self._results: dict[UUID, SemanticFractureResult] = {}

    def get(self, artifact_id: UUID) -> SemanticFractureResult | None:
        return self._results.get(artifact_id)

    def analyze(
        self,
        artifact: ArtifactMetadata,
        fastscan: FastScanResult,
        interpretation: InterpretationResult,
        graph: InterpretationGraph,
    ) -> SemanticFractureResult:
        self._results.pop(artifact.artifact_id, None)
        result = self.classify(artifact, fastscan, interpretation, graph)
        self._results[artifact.artifact_id] = result
        return result

    def classify(
        self,
        artifact: ArtifactMetadata,
        fastscan: FastScanResult,
        interpretation: InterpretationResult,
        graph: InterpretationGraph,
    ) -> SemanticFractureResult:
        if (
            not (artifact.artifact_id == fastscan.artifact_id == interpretation.artifact_id == graph.artifact_id)
            or not (artifact.sha256 == fastscan.sha256 == interpretation.sha256 == graph.sha256)
            or not fastscan.integrity.sha256_matches_ingestion
            or not (fastscan.observed.detected_type == interpretation.artifact_family == graph.artifact_family)
        ):
            raise EvidenceIntegrityError("Artifact, FastScan, interpretation, and graph evidence do not describe the same verified bytes")

        fractures = []
        consumers = interpretation.interpreters
        if len(consumers) >= 2:
            left, right = consumers[:2]
            names = [left.interpreter, right.interpreter]
            if left.interpreter != right.interpreter:
                for code, family, field, classification, severity, rationale in RULES:
                    if family is not None and family != interpretation.artifact_family:
                        continue
                    if field == "identity" and not (left.recognized and right.recognized):
                        continue
                    if field not in ("identity", "valid") and not (left.valid and right.valid):
                        continue
                    if field in ("entry_name_set", "duplicate_entry_names") and not comparable_zip_names(left.warnings, right.warnings):
                        continue
                    a, b = _values(left, right, field)
                    if a is None or b is None or a == b:
                        continue
                    expected = {left.interpreter: a, right.interpreter: b}
                    signal = next((item for item in interpretation.signals
                                   if item.code == code and item.interpreters == names and item.values == expected), None)
                    if signal is None:
                        continue
                    evidence = {"values": expected}
                    if field == "valid":
                        evidence["parser_results"] = {
                            item.interpreter: {
                                "recognized": item.recognized,
                                "identity": item.identity,
                                "valid": item.valid,
                                "errors": item.errors,
                            }
                            for item in (left, right)
                        }
                    fractures.append(FractureRecord(
                        id=f"fracture:{artifact.artifact_id}:{classification.value.lower()}:{field}",
                        classification=classification,
                        severity=severity,
                        source_signal=code,
                        interpreters=names,
                        evidence=evidence,
                        graph_node_ids=_graph_refs(graph, names, field),
                        rationale=rationale,
                    ))

        context = [ContextSignal(code=item.code, severity=item.severity, message=item.message)
                   for item in fastscan.signals]
        highest = "HIGH" if any(item.severity == "HIGH" for item in fractures) else (
            "MEDIUM" if fractures else None
        )
        return SemanticFractureResult(
            artifact_id=artifact.artifact_id,
            sha256=artifact.sha256,
            fracture_detected=bool(fractures),
            fractures=fractures,
            context_signals=context,
            summary=FractureSummary(fracture_count=len(fractures), highest_severity=highest),
        )
