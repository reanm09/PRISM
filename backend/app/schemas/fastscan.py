from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ObservedIdentity(BaseModel):
    detected_type: str
    detected_mime: str
    magic_description: str


class ExtensionConsistency(BaseModel):
    extension_matches_observed: bool | None


class Statistics(BaseModel):
    entropy: float


class HeaderEvidence(BaseModel):
    first_bytes_hex: str


class IntegrityEvidence(BaseModel):
    sha256_matches_ingestion: bool


class FastScanSignal(BaseModel):
    code: str
    severity: Literal["INFO", "WARNING", "ERROR"]
    message: str


class PDFStructuralFeatures(BaseModel):
    family: Literal["PDF"] = "PDF"
    eof_marker_present: bool
    startxref_present: bool
    startxref_offset_in_bounds: bool | None
    eof_marker_count: int
    trailing_bytes_after_final_eof: int | None


class ZIPStructuralFeatures(BaseModel):
    family: Literal["ZIP"] = "ZIP"
    local_central_name_mismatch_count: int | None
    central_directory_entry_count: int | None


class PNGStructuralFeatures(BaseModel):
    family: Literal["PNG"] = "PNG"
    iend_present: bool | None
    crc_error_count: int | None
    structure_complete: bool | None


class PDFSecurityPrecursors(BaseModel):
    family: Literal["PDF"] = "PDF"
    javascript_action_candidate_count: int | None
    launch_action_candidate_count: int | None
    richmedia_annotation_candidate_count: int | None
    syntax_scan_complete: bool


class ZIPSecurityPrecursors(BaseModel):
    family: Literal["ZIP"] = "ZIP"
    parent_traversal_entry_candidate_count: int | None
    absolute_path_entry_candidate_count: int | None
    directory_scan_complete: bool


class FastScanResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: UUID
    sha256: str
    size_bytes: int
    claimed_extension: str
    observed: ObservedIdentity
    consistency: ExtensionConsistency
    statistics: Statistics
    header: HeaderEvidence
    integrity: IntegrityEvidence
    signals: list[FastScanSignal]
    structural_features: PDFStructuralFeatures | ZIPStructuralFeatures | PNGStructuralFeatures | None = None
    pretriage_security_features: PDFSecurityPrecursors | ZIPSecurityPrecursors | None = None
    scan_status: Literal["COMPLETE"] = "COMPLETE"
