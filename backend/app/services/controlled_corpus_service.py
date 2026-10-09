import asyncio
import hashlib
import io
import json
import zipfile
from collections import Counter
from pathlib import Path

from fastapi import UploadFile
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, FloatObject, NameObject, TextStringObject

from app.core.config import Settings
from app.schemas.fracture_dataset import GroundTruthProvenance
from app.services.artifact_service import ArtifactService
from app.services.fastscan_service import FastScanService
from app.services.fracture_dataset_service import FractureDatasetService
from app.services.interpretation_graph_service import InterpretationGraphService
from app.services.interpretation_service import InterpretationService
from app.services.semantic_fracture_service import SemanticFractureService
from app.services.suspicious_evidence_service import derive_suspicious_evidence
from app.services.laya_training_service import LayaTrainingService, validate_model_input


CORPUS_NAME = "PRISM-CONTROLLED-HARMLESS"
CORPUS_VERSION = "1.0"
KINDS = (
    ("baseline", "CONTROLLED_HARMLESS_BASELINE", 10),
    ("mismatch", "CONTROLLED_HARMLESS_CLAIM_MISMATCH", 5),
)
FAMILIES = ("PDF", "ZIP", "PNG")
EXTENSIONS = {"PDF": ".pdf", "ZIP": ".zip", "PNG": ".png"}


def _pdf_bytes(index: int, kind: str) -> bytes:
    writer = PdfWriter()
    for _ in range(1 + index % 3):
        writer.add_blank_page(width=200 + index, height=280 + index)
    writer.add_metadata({"/Title": f"PRISM controlled {kind} PDF {index:04d}"})
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _zip_bytes(index: int, kind: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for entry in range(1 + index % 4):
            name = f"folder/note_{entry}.txt" if entry % 2 else f"note_{entry}.txt"
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, f"PRISM controlled {kind} ZIP {index:04d} entry {entry}\n")
    return output.getvalue()


def _png_bytes(index: int, kind: str) -> bytes:
    width, height = 4 + index, 3 + index
    category_offset = 0 if kind == "baseline" else 101
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            pixels[x, y] = ((index * 17 + x * 13 + category_offset) % 256,
                            (y * 29 + index) % 256, (x + y + index * 7) % 256)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


GENERATORS = {"PDF": _pdf_bytes, "ZIP": _zip_bytes, "PNG": _png_bytes}

SUSPICIOUS_REASONS = (
    "PDF_JAVASCRIPT_ACTION", "PDF_LAUNCH_ACTION", "PDF_RICHMEDIA_CONTENT",
    "ZIP_PATH_TRAVERSAL_ENTRY", "ZIP_ABSOLUTE_PATH_ENTRY",
)
SUSPICIOUS_OBSERVATIONS = {
    "PDF_JAVASCRIPT_ACTION": "javascript_action_count",
    "PDF_LAUNCH_ACTION": "launch_action_count",
    "PDF_RICHMEDIA_CONTENT": "richmedia_count",
    "ZIP_PATH_TRAVERSAL_ENTRY": "path_traversal_entry_count",
    "ZIP_ABSOLUTE_PATH_ENTRY": "absolute_path_entry_count",
}


def _suspicious_pdf_bytes(reason: str, index: int) -> bytes:
    writer = PdfWriter()
    seed = f"{reason.lower()}_{index:04d}"
    for page_index in range(1 + index % 3):
        page = writer.add_blank_page(width=210 + index * 3, height=290 + page_index)
        font = writer._add_object(DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }))
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
        })
        stream = DecodedStreamObject()
        stream.set_data(
            f"BT /F1 12 Tf 20 40 Td (PRISM CONTROLLED {seed} PAGE {page_index}) Tj ET".encode("ascii")
        )
        page[NameObject("/Contents")] = writer._add_object(stream)
        if reason == "PDF_RICHMEDIA_CONTENT" and page_index == 0:
            annotation = DictionaryObject({
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/RichMedia"),
                NameObject("/Rect"): ArrayObject([FloatObject(0), FloatObject(0), FloatObject(12), FloatObject(12)]),
                NameObject("/NM"): TextStringObject(seed),
            })
            page[NameObject("/Annots")] = ArrayObject([writer._add_object(annotation)])
    writer.add_metadata({"/Title": f"PRISM controlled suspicious {seed}", "/Subject": f"Independent seed {index}"})
    if reason in ("PDF_JAVASCRIPT_ACTION", "PDF_LAUNCH_ACTION"):
        action = DictionaryObject({
            NameObject("/Type"): NameObject("/Action"),
            NameObject("/S"): NameObject("/JavaScript" if reason == "PDF_JAVASCRIPT_ACTION" else "/Launch"),
        })
        if reason == "PDF_JAVASCRIPT_ACTION":
            action[NameObject("/JS")] = TextStringObject("void(0);")
        else:
            action[NameObject("/F")] = TextStringObject(f"nonexistent-placeholder-{seed}.txt")
        writer._root_object[NameObject("/OpenAction")] = writer._add_object(action)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _suspicious_zip_bytes(reason: str, index: int) -> bytes:
    if reason == "ZIP_PATH_TRAVERSAL_ENTRY":
        hazard = (
            f"../outside_{index:04d}.txt",
            f"folder/../../outside_{index:04d}.txt",
            f"..\\outside_{index:04d}.txt",
            f"folder\\..\\..\\outside_{index:04d}.txt",
        )[index - 1]
    else:
        hazard = (
            f"/root/absolute_{index:04d}.txt",
            f"C:/root/absolute_{index:04d}.txt",
            f"C:\\root\\absolute_{index:04d}.txt",
            f"\\\\server\\share\\absolute_{index:04d}.txt",
        )[index - 1]
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        names = [f"docs/note_{index}_{entry}.txt" for entry in range(1 + index % 3)] + [hazard]
        for entry, name in enumerate(names):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, f"PRISM controlled {reason} independent seed {index} entry {entry}\n")
    return output.getvalue()


class ControlledCorpusService:
    def __init__(self, settings: Settings):
        self.root = settings.fracture_root / "controlled"
        self.artifacts_root = self.root / "artifacts"
        if not self.root.resolve().is_relative_to(settings.fracture_root.resolve()):
            raise ValueError("Controlled corpus leaves PRISM fracture root")
        self.artifacts = ArtifactService(settings)
        self.fastscan = FastScanService(settings.artifact_storage)
        self.interpretation = InterpretationService(settings.artifact_storage, settings.max_upload_bytes)
        self.graph = InterpretationGraphService()
        self.fracture = SemanticFractureService()
        self.dataset = FractureDatasetService(settings.fracture_root)

    def build(self) -> dict:
        self.artifacts_root.mkdir(parents=True, exist_ok=True)
        records_root = self.dataset.fracture_root / "records"
        before = sum(1 for _ in records_root.glob("pf_*.json")) if records_root.is_dir() else 0
        entries = []
        seen_hashes = set()
        processed = reused = 0
        for family in FAMILIES:
            for kind, provenance_source, count in KINDS:
                for index in range(1, count + 1):
                    sample_id = f"controlled:{family.lower()}:{kind}:{index:04d}"
                    extension = EXTENSIONS[family] if kind == "baseline" else (".dat" if index % 2 else ".bin")
                    filename = f"{family.lower()}_{kind}_{index:04d}{extension}"
                    data = GENERATORS[family](index, kind)
                    sha256 = hashlib.sha256(data).hexdigest()
                    if sha256 in seen_hashes:
                        raise ValueError(f"Duplicate controlled bytes: {sample_id}")
                    seen_hashes.add(sha256)
                    path = self.artifacts_root / filename
                    if path.exists():
                        if path.read_bytes() != data:
                            raise ValueError(f"Existing controlled artifact differs: {filename}")
                    else:
                        with path.open("xb") as output:
                            output.write(data)
                    provenance = GroundTruthProvenance(
                        source=provenance_source, corpus=CORPUS_NAME,
                        corpus_version=CORPUS_VERSION, sample_id=sample_id,
                    )
                    record_id = self.dataset.sample_id(sha256, extension)
                    record_path = records_root / f"{record_id}.json"
                    if record_path.exists():
                        record = self.dataset.read(record_id)
                        if record.artifact.sha256 != sha256 or record.ground_truth_provenance != provenance:
                            raise ValueError(f"Existing PRISM-Fracture record conflicts with {sample_id}")
                        reused += 1
                    else:
                        with path.open("rb") as source:
                            artifact = asyncio.run(self.artifacts.ingest(UploadFile(file=source, filename=filename)))
                        if artifact.sha256 != sha256:
                            raise ValueError(f"Ingestion hash changed for {sample_id}")
                        scan = self.fastscan.scan(artifact)
                        if scan.observed.detected_type != family:
                            raise ValueError(f"FastScan identity mismatch for {sample_id}")
                        interpretation = self.interpretation.interpret(artifact, family)
                        graph = self.graph.build(artifact, scan, interpretation)
                        fracture = self.fracture.analyze(artifact, scan, interpretation, graph)
                        record = self.dataset.build(artifact, scan, interpretation, graph, fracture, provenance)
                        self.dataset.export(record)
                        processed += 1
                    fastscan_codes = {signal.code for signal in record.fastscan.signals}
                    expected_match = kind == "baseline"
                    errors = []
                    if record.fastscan.observed_type != family:
                        errors.append("OBSERVED_IDENTITY_MISMATCH")
                    if record.fastscan.extension_matches_observed is not expected_match:
                        errors.append("CLAIM_CONSISTENCY_MISMATCH")
                    if not expected_match and "EXTENSION_TYPE_MISMATCH" not in fastscan_codes:
                        errors.append("EXTENSION_TYPE_MISMATCH_SIGNAL_MISSING")
                    if not all(item.valid for item in record.interpretation.interpreters):
                        errors.append("INTERPRETER_REJECTED_CONTROLLED_ARTIFACT")
                    entries.append({
                        "sample_id": sample_id,
                        "corpus_name": CORPUS_NAME,
                        "corpus_version": CORPUS_VERSION,
                        "provenance": provenance_source,
                        "family": family,
                        "filename": filename,
                        "sha256": sha256,
                        "expected_identity": family,
                        "expected_claim_match": expected_match,
                        "verified": not errors,
                        "verification_errors": errors,
                        "fracture_detected": record.fracture.fracture_detected,
                        "dataset_sample_id": record.sample_id,
                    })
        manifest_path = self.root / "manifest.jsonl"
        content = "".join(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for item in entries)
        if manifest_path.exists():
            if manifest_path.read_text(encoding="utf-8") != content:
                raise ValueError("Existing controlled manifest differs; refusing to overwrite")
        else:
            with manifest_path.open("x", encoding="utf-8", newline="\n") as output:
                output.write(content)
        after = sum(1 for _ in records_root.glob("pf_*.json"))
        return {
            "generated": len(entries),
            "processed": processed,
            "reused": reused,
            "verified": sum(item["verified"] for item in entries),
            "verification_failures": sum(not item["verified"] for item in entries),
            "unexpected_fractures": [item["sample_id"] for item in entries if item["fracture_detected"]],
            "records_before": before,
            "records_after": after,
            "by_family": {
                family: {
                    kind: {
                        "generated": sum(item["family"] == family and item["provenance"] == source for item in entries),
                        "verified": sum(item["family"] == family and item["provenance"] == source and item["verified"] for item in entries),
                        "failed": sum(item["family"] == family and item["provenance"] == source and not item["verified"] for item in entries),
                    }
                    for kind, source, _ in KINDS
                }
                for family in FAMILIES
            },
        }

    def build_suspicious_campaign(self) -> dict:
        campaign_root = self.root / "suspicious-v1"
        artifacts_root = campaign_root / "artifacts"
        artifacts_root.mkdir(parents=True, exist_ok=True)
        records_root = self.dataset.fracture_root / "records"
        before = sum(1 for _ in records_root.glob("pf_*.json")) if records_root.is_dir() else 0
        entries = []
        hashes = set()
        processed = reused = 0
        laya = LayaTrainingService()
        for reason in SUSPICIOUS_REASONS:
            family = reason.split("_", 1)[0]
            for index in range(1, 5):
                probe_id = f"{reason.lower()}_{index:04d}"
                filename = f"{probe_id}{'.pdf' if family == 'PDF' else '.zip'}"
                lineage = f"lineage:suspicious-v1:{probe_id}"
                data = (_suspicious_pdf_bytes(reason, index) if family == "PDF"
                        else _suspicious_zip_bytes(reason, index))
                sha256 = hashlib.sha256(data).hexdigest()
                if sha256 in hashes:
                    raise ValueError(f"Duplicate candidate bytes: {probe_id}")
                hashes.add(sha256)
                path = artifacts_root / filename
                if path.exists():
                    if path.read_bytes() != data:
                        raise ValueError(f"Existing candidate differs from deterministic bytes: {probe_id}")
                else:
                    with path.open("xb") as output:
                        output.write(data)
                provenance = GroundTruthProvenance(
                    source="CONTROLLED_SUSPICIOUS_RESEARCH", corpus="PRISM-SUSPICIOUS",
                    corpus_version="1.0", sample_id=f"suspicious:{probe_id}",
                    lineage_group_id=lineage,
                )
                entry = {
                    "probe_id": probe_id, "family": family, "intended_reason_code": reason,
                    "filename": filename, "sha256": sha256, "lineage_group_id": lineage,
                }
                try:
                    record_id = self.dataset.sample_id(sha256, path.suffix)
                    record_path = records_root / f"{record_id}.json"
                    if record_path.exists():
                        record = self.dataset.read(record_id)
                        if record.artifact.sha256 != sha256 or record.ground_truth_provenance != provenance:
                            raise ValueError("Existing source record conflicts with deterministic candidate")
                        reused += 1
                    else:
                        with path.open("rb") as source:
                            artifact = asyncio.run(self.artifacts.ingest(UploadFile(file=source, filename=filename)))
                        if artifact.sha256 != sha256:
                            raise ValueError("INGESTED_SHA256_MISMATCH")
                        scan = self.fastscan.scan(artifact)
                        if not scan.integrity.sha256_matches_ingestion or scan.observed.detected_type != family:
                            raise ValueError("FASTSCAN_IDENTITY_OR_INTEGRITY_FAILURE")
                        interpretation = self.interpretation.interpret(artifact, family)
                        graph = self.graph.build(artifact, scan, interpretation)
                        fracture = self.fracture.analyze(artifact, scan, interpretation, graph)
                        suspicious = derive_suspicious_evidence(interpretation)
                        if suspicious is None or not suspicious.verified or suspicious.source != "DETERMINISTIC_SECURITY_OBSERVATION":
                            raise ValueError("STRUCTURED_SECURITY_OBSERVATION_NOT_VERIFIED")
                        observed = next(item for item in interpretation.interpreters
                                        if item.interpreter == ("pypdf" if family == "PDF" else "zipfile"))
                        if not observed.valid or getattr(observed.observations, SUSPICIOUS_OBSERVATIONS[reason]) is None or getattr(observed.observations, SUSPICIOUS_OBSERVATIONS[reason]) <= 0:
                            raise ValueError("EXPECTED_STRUCTURED_OBSERVATION_MISSING")
                        if suspicious.reason_codes != [reason]:
                            raise ValueError(f"UNEXPECTED_DERIVED_REASON_CODES: {suspicious.reason_codes}")
                        if fracture.fracture_detected:
                            raise ValueError("UNEXPECTED_SEMANTIC_FRACTURE")
                        record = self.dataset.build(
                            artifact, scan, interpretation, graph, fracture,
                            ground_truth_provenance=provenance, suspicious_evidence=suspicious,
                        )
                        candidate = laya.build(record)
                        if not candidate.eligibility.eligible or candidate.record is None or candidate.record.targets.artifact_state != "SUSPICIOUS":
                            raise ValueError("LAYA_SUSPICIOUS_ADMISSION_FAILED")
                        validate_model_input(candidate.record.model_input.model_dump(mode="json"))
                        self.dataset.export(record)
                        processed += 1
                    derived = derive_suspicious_evidence(
                        record.interpretation, record.artifact.artifact_id
                    )
                    if record.suspicious_evidence != derived or record.suspicious_evidence.reason_codes != [reason]:
                        raise ValueError("STORED_SUSPICIOUS_EVIDENCE_MISMATCH")
                    candidate = laya.build(record)
                    if candidate.record is None or candidate.record.targets.artifact_state != "SUSPICIOUS":
                        raise ValueError("STORED_LAYA_TARGET_MISMATCH")
                    entry.update(status="ADMITTED", dataset_sample_id=record.sample_id,
                                 observed_reason_codes=record.suspicious_evidence.reason_codes,
                                 fracture_detected=record.fracture.fracture_detected)
                except Exception as exc:
                    entry.update(status="REJECTED", rejection_reason=f"{type(exc).__name__}: {str(exc)[:200]}")
                entries.append(entry)
        content = "".join(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
                          for item in entries)
        manifest_path = campaign_root / "manifest.jsonl"
        if manifest_path.exists():
            if manifest_path.read_text(encoding="utf-8") != content:
                raise ValueError("Existing suspicious campaign manifest differs")
        else:
            with manifest_path.open("x", encoding="utf-8", newline="\n") as output:
                output.write(content)
        after = sum(1 for _ in records_root.glob("pf_*.json"))
        lineage_sizes = Counter(item["lineage_group_id"] for item in entries if item["status"] == "ADMITTED")
        return {
            "attempted": len(entries),
            "admitted": sum(item["status"] == "ADMITTED" for item in entries),
            "processed": processed, "reused": reused,
            "rejected": [item for item in entries if item["status"] == "REJECTED"],
            "unexpected_fractures": [item["probe_id"] for item in entries
                                     if "UNEXPECTED_SEMANTIC_FRACTURE" in item.get("rejection_reason", "")],
            "reason_counts": {reason: sum(item["status"] == "ADMITTED" and
                                          item["intended_reason_code"] == reason for item in entries)
                              for reason in SUSPICIOUS_REASONS},
            "unique_sha256": len(hashes),
            "lineage_groups": len(lineage_sizes),
            "largest_lineage_size": max(lineage_sizes.values(), default=0),
            "source_records_before": before,
            "source_records_after": after,
        }
