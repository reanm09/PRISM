from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InterpretationObservations(BaseModel):
    page_count: int | None = None
    encrypted: bool | None = None
    metadata_present: bool | None = None
    embedded_files_detected: bool | None = None
    javascript_action_count: int | None = None
    launch_action_count: int | None = None
    richmedia_count: int | None = None
    entry_count: int | None = None
    total_uncompressed_size: int | None = None
    directory_entries: int | None = None
    encrypted_entries: int | None = None
    entry_names: list[str] | None = None
    duplicate_entry_names: list[str] | None = None
    path_traversal_entry_count: int | None = None
    absolute_path_entry_count: int | None = None
    width: int | None = None
    height: int | None = None
    color_mode: str | None = None
    frame_count: int | None = None


PdfObservations = InterpretationObservations


class InterpreterResult(BaseModel):
    interpreter: str
    interpreter_version: str
    recognized: bool
    identity: str | None
    valid: bool
    observations: InterpretationObservations
    warnings: list[str]
    errors: list[str]


class Agreement(BaseModel):
    identity: bool | None
    validity: bool
    page_count: bool | None = None
    encrypted: bool | None = None
    entry_count: bool | None = None
    total_uncompressed_size: bool | None = None
    entry_name_set: bool | None = None
    duplicate_entry_names: bool | None = None
    image_dimensions: bool | None = None


ComparisonStatus = Literal[
    "AGREEMENT",
    "DISAGREEMENT",
    "NOT_COMPARABLE",
]


class PropertyComparison(BaseModel):
    property_name: str
    signal_code: str
    status: ComparisonStatus
    interpreters: list[str]
    values: dict[str, Any]
    reason: str | None = None


class ComparisonCoverage(BaseModel):
    total: int = 0
    agreement_count: int = 0
    disagreement_count: int = 0
    not_comparable_count: int = 0


class InterpretationComparison(BaseModel):
    interpreters_run: int
    interpreters_recognized: int
    interpreters_valid: int

    # Legacy compact agreement contract retained for fracture/dataset
    # compatibility. None continues to mean the old "not compared" state.
    agreement: Agreement

    # Rich deterministic comparison contract.
    properties: list[PropertyComparison] = Field(default_factory=list)
    coverage: ComparisonCoverage = Field(default_factory=ComparisonCoverage)


class DisagreementSignal(BaseModel):
    code: str
    interpreters: list[str]
    values: dict[str, str | int | bool | list[str]]


class InterpretationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: UUID
    sha256: str
    artifact_family: Literal["PDF", "ZIP", "PNG"]
    interpreters: list[InterpreterResult]
    comparison: InterpretationComparison
    signals: list[DisagreementSignal]
    status: Literal["COMPLETE"] = "COMPLETE"
