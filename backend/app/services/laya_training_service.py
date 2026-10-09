from app.core.config import settings
from app.schemas.artifact import ArtifactMetadata
from app.schemas.fracture_dataset import DatasetRecord, SCHEMA_VERSION
from app.schemas.laya_triage import (
    GroundTruthEvidence,
    LabelProvenance,
    LayaModelInput,
    LayaTargets,
    LayaTrainingCandidate,
    LayaTrainingRecord,
    TrainingEligibility,
)
from app.services.fracture_dataset_service import FractureDatasetService
from app.services.fastscan_service import FastScanService
from app.services.suspicious_evidence_service import derive_suspicious_evidence


AMBIGUITY_SIGNALS = {"EXTENSION_TYPE_MISMATCH", "UNKNOWN_FILE_TYPE"}
FORBIDDEN_MODEL_INPUT_KEYS = frozenset({
    "interpretation_signals", "interpreter_count", "recognized_count", "valid_count",
    "parser_agreement", "fracture_type", "fracture_types", "fracture_severity",
    "fracture_detected", "semantic_fracture", "recommended_action",
    "interpreter_observations", "observations", "graph_nodes", "graph_edges",
    "nodes", "edges", "artifact_id", "source_record_id", "sha256", "targets",
    "label_provenance", "ground_truth_provenance", "controlled_source",
    "lineage_group_id", "split_group_id", "suspicious_evidence", "reason_codes",
})


class PostTriageFeatureLeakageError(ValueError):
    pass


def validate_model_input(value: object) -> None:
    if isinstance(value, dict):
        leaked = FORBIDDEN_MODEL_INPUT_KEYS.intersection(value)
        if leaked:
            raise PostTriageFeatureLeakageError(
                f"POST_TRIAGE_FEATURE_LEAKAGE: {', '.join(sorted(leaked))}"
            )
        for nested in value.values():
            validate_model_input(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            validate_model_input(nested)


def _evidence_is_consistent(source: DatasetRecord) -> bool:
    fracture = source.fracture
    actual_types = sorted({item.classification for item in fracture.fractures})
    actual_severity = "HIGH" if any(item.severity == "HIGH" for item in fracture.fractures) else (
        "MEDIUM" if fracture.fractures else None
    )
    signal_codes = {item.code for item in source.interpretation.signals}
    suspicious = source.suspicious_evidence
    suspicious_family_matches = suspicious is None or all(
        code.startswith(f"{source.interpretation.artifact_family}_")
        for code in suspicious.reason_codes
    )
    return (
        source.schema_version == SCHEMA_VERSION
        and source.sample_id == FractureDatasetService.sample_id(
            source.artifact.sha256, source.artifact.claimed_extension
        )
        and source.fastscan.sha256_matches_ingestion
        and source.fastscan.observed_type == source.interpretation.artifact_family
        and fracture.fracture_detected == bool(fracture.fractures)
        and fracture.fracture_count == len(fracture.fractures)
        and fracture.fracture_types == actual_types
        and fracture.highest_severity == actual_severity
        and all(item.source_signal in signal_codes for item in fracture.fractures)
        and suspicious_family_matches
        and (suspicious is None or not suspicious.verified or
             suspicious == derive_suspicious_evidence(source.interpretation, source.artifact.artifact_id))
    )


class LayaTrainingService:
    def build(self, source: DatasetRecord) -> LayaTrainingCandidate:
        if not _evidence_is_consistent(source):
            return LayaTrainingCandidate(
                source_record_id=source.sample_id,
                eligibility=TrainingEligibility(eligible=False, reasons=["INCONSISTENT_SOURCE_EVIDENCE"]),
                record=None,
            )

        fracture = source.fracture
        provenance = source.ground_truth_provenance
        suspicious = source.suspicious_evidence
        fastscan_codes = {item.code for item in source.fastscan.signals}
        if fracture.fracture_detected:
            targets = LayaTargets(
                artifact_state="FRACTURED", escalation="PRISM_LAB",
                fracture_target=1, priority=fracture.highest_severity,
            )
            rules = ["VERIFIED_SEMANTIC_FRACTURE"]
        elif suspicious is not None and suspicious.verified:
            targets = LayaTargets(
                artifact_state="SUSPICIOUS", escalation="PRISM_LAB",
                fracture_target=0, priority="HIGH",
            )
            rules = ["VERIFIED_DETERMINISTIC_SUSPICIOUS_EVIDENCE"]
        elif provenance is not None and provenance.source == "CONTROLLED_HARMLESS_CLAIM_MISMATCH" and "EXTENSION_TYPE_MISMATCH" not in fastscan_codes:
            return LayaTrainingCandidate(
                source_record_id=source.sample_id,
                eligibility=TrainingEligibility(eligible=False, reasons=["CONTROLLED_CLAIM_MISMATCH_NOT_OBSERVED"]),
                record=None,
            )
        elif fastscan_codes.intersection(AMBIGUITY_SIGNALS):
            targets = LayaTargets(
                artifact_state="AMBIGUOUS", escalation="DEEP_SCAN",
                fracture_target=0, priority="MEDIUM",
            )
            rules = ["FASTSCAN_AMBIGUITY_SIGNAL"]
        elif provenance is not None and provenance.source == "CONTROLLED_HARMLESS_BASELINE" and source.fastscan.extension_matches_observed is True:
            targets = LayaTargets(
                artifact_state="BENIGN", escalation="PASS",
                fracture_target=0, priority="LOW",
            )
            rules = ["VERIFIED_CONTROLLED_HARMLESS_BASELINE"]
        else:
            return LayaTrainingCandidate(
                source_record_id=source.sample_id,
                eligibility=TrainingEligibility(
                    eligible=False, reasons=["NO_AUTHORITATIVE_ARTIFACT_STATE_LABEL"]
                ),
                record=None,
            )

        artifact = ArtifactMetadata(
            artifact_id=source.artifact.artifact_id,
            sha256=source.artifact.sha256,
            original_name=source.artifact.original_name,
            size_bytes=source.artifact.size_bytes,
            claimed_extension=source.artifact.claimed_extension,
        )
        path = settings.artifact_storage / str(artifact.artifact_id)
        if not path.is_file():
            raise ValueError(f"V3_BACKFILL_BLOCKED: exact artifact bytes unavailable for {source.sample_id}")
        fresh_scan = FastScanService(settings.artifact_storage).scan(artifact)
        if (not fresh_scan.integrity.sha256_matches_ingestion
                or fresh_scan.size_bytes != artifact.size_bytes
                or fresh_scan.structural_features is None):
            raise ValueError(f"V3_BACKFILL_BLOCKED: byte identity or structural scan failed for {source.sample_id}")
        model_input_data = {
            "claimed_extension": source.artifact.claimed_extension,
            "observed_identity": fresh_scan.observed.detected_type,
            "mime": fresh_scan.observed.detected_mime,
            "size_bytes": fresh_scan.size_bytes,
            "entropy": fresh_scan.statistics.entropy,
            "extension_consistent": fresh_scan.consistency.extension_matches_observed,
            "fastscan_signals": [item.code for item in fresh_scan.signals],
            "structural_features": fresh_scan.structural_features.model_dump(mode="json"),
            "pretriage_security_features": (
                fresh_scan.pretriage_security_features.model_dump(mode="json")
                if fresh_scan.pretriage_security_features is not None else None
            ),
        }
        historical_input = {
            "claimed_extension": source.artifact.claimed_extension,
            "observed_identity": source.fastscan.observed_type,
            "mime": source.fastscan.observed_mime,
            "size_bytes": source.artifact.size_bytes,
            "entropy": source.fastscan.entropy,
            "extension_consistent": source.fastscan.extension_matches_observed,
            "fastscan_signals": [item.code for item in source.fastscan.signals],
        }
        if {key: model_input_data[key] for key in historical_input} != historical_input:
            raise ValueError(f"V3_BACKFILL_BLOCKED: fresh FastScan differs from source evidence for {source.sample_id}")
        try:
            validate_model_input(model_input_data)
        except PostTriageFeatureLeakageError:
            return LayaTrainingCandidate(
                source_record_id=source.sample_id,
                eligibility=TrainingEligibility(eligible=False, reasons=["POST_TRIAGE_FEATURE_LEAKAGE"]),
                record=None,
            )
        record = LayaTrainingRecord(
            record_id=f"laya:{source.sample_id}",
            source_record_id=source.sample_id,
            artifact_id=source.artifact.artifact_id,
            sha256=source.artifact.sha256,
            split_group_id=(provenance.lineage_group_id if provenance and provenance.lineage_group_id
                            else source.artifact.sha256),
            source_family=source.interpretation.artifact_family,
            model_input=LayaModelInput(**model_input_data),
            targets=targets,
            label_provenance=LabelProvenance(
                rules=rules,
                controlled_source=provenance,
                suspicious_evidence=suspicious,
                ground_truth_evidence=GroundTruthEvidence(
                    fracture_detected=fracture.fracture_detected,
                    fracture_types=fracture.fracture_types,
                    fracture_severity=fracture.highest_severity,
                ),
            ),
        )
        return LayaTrainingCandidate(
            source_record_id=source.sample_id,
            eligibility=TrainingEligibility(eligible=True, reasons=[]),
            record=record,
        )
