
from uuid import UUID

from app.schemas.fracture_dataset import DatasetInterpretation, SuspiciousEvidence
from app.schemas.interpretation import InterpretationResult


OBSERVATION_REASONS = {
    "PDF": ("pypdf", (
        ("javascript_action_count", "PDF_JAVASCRIPT_ACTION"),
        ("launch_action_count", "PDF_LAUNCH_ACTION"),
        ("richmedia_count", "PDF_RICHMEDIA_CONTENT"),
    )),
    "ZIP": ("zipfile", (
        ("path_traversal_entry_count", "ZIP_PATH_TRAVERSAL_ENTRY"),
        ("absolute_path_entry_count", "ZIP_ABSOLUTE_PATH_ENTRY"),
    )),
}


def derive_suspicious_evidence(
    interpretation: InterpretationResult | DatasetInterpretation,
    artifact_id: UUID | None = None,
) -> SuspiciousEvidence | None:
    mapping = OBSERVATION_REASONS.get(interpretation.artifact_family)
    if mapping is None:
        return None
    interpreter_name, fields = mapping
    result = next((item for item in interpretation.interpreters if item.interpreter == interpreter_name), None)
    if result is None or not result.recognized or not result.valid or result.identity != interpretation.artifact_family:
        return None
    values = [getattr(result.observations, field) for field, _ in fields]
    if any(value is None or value < 0 for value in values):
        return None
    codes = [code for value, (_, code) in zip(values, fields) if value > 0]
    if not codes:
        return None
    resolved_id = getattr(interpretation, "artifact_id", artifact_id)
    if resolved_id is None:
        raise ValueError("Artifact ID is required for suspicious evidence references")
    return SuspiciousEvidence(
        verified=True,
        source="DETERMINISTIC_SECURITY_OBSERVATION",
        reason_codes=codes,
        evidence_refs=[
            f"observation:{resolved_id}:{interpreter_name}:{field}"
            for value, (field, _) in zip(values, fields) if value > 0
        ],
    )
