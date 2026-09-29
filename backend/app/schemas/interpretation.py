from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class InterpretationObservations(BaseModel):
    page_count: int | None = None
    encrypted: bool | None = None
    metadata_present: bool | None = None
    embedded_files_detected: bool | None = None
    entry_count: int | None = None
    total_uncompressed_size: int | None = None
    directory_entries: int | None = None
    encrypted_entries: int | None = None
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
    image_dimensions: bool | None = None


class InterpretationComparison(BaseModel):
    interpreters_run: int
    interpreters_recognized: int
    interpreters_valid: int
    agreement: Agreement


class DisagreementSignal(BaseModel):
    code: str
    interpreters: list[str]
    values: dict[str, str | int | bool]


class InterpretationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: UUID
    sha256: str
    artifact_family: Literal["PDF", "ZIP", "PNG"]
    interpreters: list[InterpreterResult]
    comparison: InterpretationComparison
    signals: list[DisagreementSignal]
    status: Literal["COMPLETE"] = "COMPLETE"
