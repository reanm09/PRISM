
import asyncio
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

from fastapi import UploadFile

from app.core.config import Settings
from app.services.artifact_service import ArtifactService
from app.services.fastscan_service import FastScanService
from app.services.fracture_dataset_service import FractureDatasetService
from app.services.interpretation_graph_service import InterpretationGraphService
from app.services.interpretation_service import InterpretationService
from app.services.semantic_fracture_service import SemanticFractureService


PROBE_ID = re.compile(r"[a-z0-9_]+\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_ARTIFACT_BYTES = 1_000_000
OBSERVATION_FIELDS = {
    "PDF": ("page_count", "encrypted", "metadata_present"),
    "ZIP": ("entry_count", "total_uncompressed_size", "directory_entries", "encrypted_entries"),
    "PNG": ("width", "height", "color_mode", "frame_count"),
}


class ProbeCorpusService:
    def __init__(self, settings: Settings):
        self.root = settings.fracture_root / "controlled-probes"
        if not self.root.resolve().is_relative_to(settings.fracture_root.resolve()):
            raise ValueError("Controlled-probes directory leaves PRISM_FRACTURE_ROOT")
        self.artifacts = ArtifactService(settings)
        self.fastscan = FastScanService(settings.artifact_storage)
        self.interpretation = InterpretationService(settings.artifact_storage, settings.max_upload_bytes)
        self.graph = InterpretationGraphService()
        self.fracture = SemanticFractureService()
        self.dataset = FractureDatasetService(settings.fracture_root)

    def _probe_path(self, relative_path: str) -> Path:
        if "\\" in relative_path or ":" in relative_path:
            raise ValueError("Probe path must be a relative POSIX path")
        relative = PurePosixPath(relative_path)
        if relative.is_absolute() or not relative.parts or any(part in (".", "..") for part in relative.parts):
            raise ValueError("Probe path leaves the controlled-probes directory")
        path = self.root.joinpath(*relative.parts)
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise ValueError("Probe path leaves the controlled-probes directory")
        return path

    def _load_probes(self) -> list[dict]:
        manifest = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
        probes = manifest.get("probes")
        if not isinstance(probes, list) or len(probes) != 4:
            raise ValueError("Controlled corpus manifest must list exactly four probes")
        ids = set()
        for probe in probes:
            if not isinstance(probe, dict):
                raise ValueError("Invalid probe entry")
            probe_id = probe.get("probe_id")
            if not isinstance(probe_id, str) or PROBE_ID.fullmatch(probe_id) is None or probe_id in ids:
                raise ValueError("Invalid or duplicate probe_id")
            ids.add(probe_id)
            if probe.get("family") not in OBSERVATION_FIELDS or probe.get("kind") not in ("POSITIVE_CANDIDATE", "NEGATIVE_CONTROL"):
                raise ValueError("Unsupported controlled probe family or kind")
            if not isinstance(probe.get("relative_path"), str):
                raise ValueError("Invalid probe path")
            self._probe_path(probe["relative_path"])
            if not isinstance(probe.get("expected_sha256"), str) or SHA256.fullmatch(probe["expected_sha256"]) is None:
                raise ValueError("Invalid expected SHA-256")
        return probes

    def _run_probe(self, probe: dict) -> dict:
        path = self._probe_path(probe["relative_path"])
        if path.stat().st_size > MAX_ARTIFACT_BYTES:
            raise ValueError("Probe artifact exceeds the one-megabyte limit")

        digest = hashlib.sha256()
        with path.open("rb") as source:
            while chunk := source.read(65536):
                digest.update(chunk)
        actual_sha256 = digest.hexdigest()
        if actual_sha256 != probe["expected_sha256"]:
            raise ValueError(f"SHA-256 mismatch: actual {actual_sha256}")

        with path.open("rb") as source:
            artifact = asyncio.run(self.artifacts.ingest(UploadFile(file=source, filename=path.name)))
        if artifact.sha256 != actual_sha256:
            raise ValueError("Artifact bytes changed between verification and ingestion")

        fastscan = self.fastscan.scan(artifact)
        family = fastscan.observed.detected_type
        if family != probe["family"]:
            raise ValueError(f"FastScan observed {family}, manifest lists {probe['family']}")
        interpretation = self.interpretation.interpret(artifact, family)
        graph = self.graph.build(artifact, fastscan, interpretation)
        fracture = self.fracture.analyze(artifact, fastscan, interpretation, graph)
        record = self.dataset.build(artifact, fastscan, interpretation, graph, fracture)
        export = self.dataset.export(record)

        return {
            "probe_id": probe["probe_id"],
            "kind": probe["kind"],
            "sha256": actual_sha256,
            "artifact_id": str(artifact.artifact_id),
            "artifact_family": interpretation.artifact_family,
            "fastscan_observed_family": fastscan.observed.detected_type,
            "interpreters": [
                {
                    "name": item.interpreter,
                    "version": item.interpreter_version,
                    "recognized": item.recognized,
                    "valid": item.valid,
                    "observations": {
                        field: getattr(item.observations, field)
                        for field in OBSERVATION_FIELDS[family]
                    },
                    "warnings": item.warnings,
                    "errors": item.errors,
                }
                for item in interpretation.interpreters
            ],
            "signals": [item.code for item in interpretation.signals],
            "fracture_detected": fracture.fracture_detected,
            "fracture_types": sorted({item.classification.value for item in fracture.fractures}),
            "highest_severity": fracture.summary.highest_severity,
            "dataset_sample_id": export.sample_id,
            "status": "COMPLETE",
        }

    def run(self) -> dict:
        probes = self._load_probes()
        results = []
        for probe in probes:
            try:
                results.append(self._run_probe(probe))
            except Exception as exc:
                results.append({
                    "probe_id": probe["probe_id"],
                    "kind": probe["kind"],
                    "status": "FAILED",
                    "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                })
        completed = [result for result in results if result["status"] == "COMPLETE"]
        return {
            "total": len(results),
            "completed": len(completed),
            "failed": len(results) - len(completed),
            "fracture_positive": sum(result["fracture_detected"] for result in completed),
            "fracture_negative": sum(not result["fracture_detected"] for result in completed),
            "results": results,
        }
