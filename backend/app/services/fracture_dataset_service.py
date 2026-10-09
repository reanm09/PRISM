import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from app.schemas.artifact import ArtifactMetadata
from app.schemas.fastscan import FastScanResult
from app.schemas.fracture_dataset import (
    SCHEMA_VERSION,
    DatasetArtifact,
    DatasetExportResult,
    DatasetFastScan,
    DatasetFracture,
    DatasetInterpretation,
    DatasetRecord,
    GroundTruthProvenance,
    SuspiciousEvidence,
)
from app.schemas.interpretation import InterpretationResult
from app.schemas.interpretation_graph import InterpretationGraph
from app.schemas.semantic_fracture import SemanticFractureResult
from app.services.suspicious_evidence_service import derive_suspicious_evidence


SAMPLE_ID_PATTERN = re.compile(r"pf_[0-9a-f]{64}\Z")


class DatasetEvidenceError(ValueError):
    pass


class InvalidSampleIdError(ValueError):
    pass


class FractureDatasetService:
    def __init__(self, fracture_root: Path):
        self.fracture_root = fracture_root

    @staticmethod
    def sample_id(sha256: str, claimed_extension: str) -> str:
        canonical = f"{sha256.lower()}|{claimed_extension.strip().lower()}|{SCHEMA_VERSION}"
        return "pf_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def build(
        self,
        artifact: ArtifactMetadata,
        fastscan: FastScanResult,
        interpretation: InterpretationResult,
        graph: InterpretationGraph,
        fracture: SemanticFractureResult,
        ground_truth_provenance: GroundTruthProvenance | None = None,
        suspicious_evidence: SuspiciousEvidence | None = None,
    ) -> DatasetRecord:
        if (
            not (artifact.artifact_id == fastscan.artifact_id == interpretation.artifact_id
                 == graph.artifact_id == fracture.artifact_id)
            or not (artifact.sha256 == fastscan.sha256 == interpretation.sha256
                    == graph.sha256 == fracture.sha256)
            or not fastscan.integrity.sha256_matches_ingestion
            or fastscan.size_bytes != artifact.size_bytes
            or fastscan.claimed_extension != artifact.claimed_extension
            or not (fastscan.observed.detected_type == interpretation.artifact_family == graph.artifact_family)
            or fracture.summary.fracture_count != len(fracture.fractures)
            or fracture.fracture_detected != bool(fracture.fractures)
            or (suspicious_evidence is not None and
                suspicious_evidence != derive_suspicious_evidence(interpretation))
        ):
            raise DatasetEvidenceError("Pipeline evidence is inconsistent; no dataset record was written")

        return DatasetRecord(
            sample_id=self.sample_id(artifact.sha256, artifact.claimed_extension),
            artifact=DatasetArtifact(
                artifact_id=artifact.artifact_id,
                sha256=artifact.sha256,
                original_name=artifact.original_name,
                size_bytes=artifact.size_bytes,
                claimed_extension=artifact.claimed_extension,
            ),
            fastscan=DatasetFastScan(
                observed_type=fastscan.observed.detected_type,
                observed_mime=fastscan.observed.detected_mime,
                magic_description=fastscan.observed.magic_description,
                extension_matches_observed=fastscan.consistency.extension_matches_observed,
                entropy=fastscan.statistics.entropy,
                sha256_matches_ingestion=fastscan.integrity.sha256_matches_ingestion,
                signals=fastscan.signals,
            ),
            interpretation=DatasetInterpretation(
                artifact_family=interpretation.artifact_family,
                interpreters=interpretation.interpreters,
                comparison=interpretation.comparison,
                signals=interpretation.signals,
            ),
            graph_summary=graph.summary,
            fracture=DatasetFracture(
                fracture_detected=fracture.fracture_detected,
                fracture_count=fracture.summary.fracture_count,
                fracture_types=sorted({item.classification for item in fracture.fractures}),
                highest_severity=fracture.summary.highest_severity,
                fractures=fracture.fractures,
                context_signals=fracture.context_signals,
            ),
            ground_truth_provenance=ground_truth_provenance,
            suspicious_evidence=suspicious_evidence,
        )

    def export(self, record: DatasetRecord) -> DatasetExportResult:
        records = self.fracture_root / "records"
        records.mkdir(parents=True, exist_ok=True)
        if not records.resolve().is_relative_to(self.fracture_root.resolve()):
            raise DatasetEvidenceError("Dataset records directory is outside the configured root")
        destination = records / f"{record.sample_id}.json"
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n", dir=records,
                prefix=".record-", suffix=".tmp", delete=False,
            ) as output:
                temporary = Path(output.name)
                json.dump(record.model_dump(mode="json"), output, ensure_ascii=False,
                          sort_keys=True, separators=(",", ":"))
                output.write("\n")
            os.replace(temporary, destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return DatasetExportResult(
            sample_id=record.sample_id,
            artifact_id=record.artifact.artifact_id,
            sha256=record.artifact.sha256,
            fracture_detected=record.fracture.fracture_detected,
            record_path=f"records/{record.sample_id}.json",
        )

    def read(self, sample_id: str) -> DatasetRecord:
        if SAMPLE_ID_PATTERN.fullmatch(sample_id) is None:
            raise InvalidSampleIdError("Invalid sample_id")
        records = self.fracture_root / "records"
        path = records / f"{sample_id}.json"
        if (
            not records.resolve().is_relative_to(self.fracture_root.resolve())
            or not path.resolve().is_relative_to(records.resolve())
        ):
            raise InvalidSampleIdError("Dataset record path is outside the configured records directory")
        with path.open("r", encoding="utf-8") as source:
            return DatasetRecord.model_validate_json(source.read())
