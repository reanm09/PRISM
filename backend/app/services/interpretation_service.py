from pathlib import Path
from uuid import UUID

from app.interpreters.base import Interpreter
from app.interpreters.pdf.pymupdf_interpreter import PyMuPDFInterpreter
from app.interpreters.pdf.pypdf_interpreter import PypdfInterpreter
from app.interpreters.png.pillow_interpreter import PillowInterpreter
from app.interpreters.png.pymupdf_interpreter import PyMuPDFPNGInterpreter
from app.interpreters.zip.stream_unzip_interpreter import StreamUnzipInterpreter
from app.interpreters.zip.zipfile_interpreter import ZipfileInterpreter
from app.schemas.artifact import ArtifactMetadata
from app.schemas.interpretation import (
    Agreement,
    DisagreementSignal,
    InterpretationComparison,
    InterpretationResult,
    InterpreterResult,
    InterpretationObservations,
)


class InterpretationService:
    def __init__(self, storage: Path, max_uncompressed_bytes: int):
        self.storage = storage
        self.interpreters: dict[str, tuple[Interpreter, Interpreter]] = {
            "PDF": (PypdfInterpreter(), PyMuPDFInterpreter()),
            "ZIP": (ZipfileInterpreter(), StreamUnzipInterpreter(max_uncompressed_bytes)),
            "PNG": (PillowInterpreter(), PyMuPDFPNGInterpreter()),
        }
        self._results: dict[UUID, InterpretationResult] = {}

    def get(self, artifact_id: UUID) -> InterpretationResult | None:
        return self._results.get(artifact_id)

    def interpret(self, artifact: ArtifactMetadata, family: str) -> InterpretationResult:
        path = self.storage / str(artifact.artifact_id)
        if not path.is_file():
            raise FileNotFoundError(path)

        results = []
        for interpreter in self.interpreters[family]:
            try:
                results.append(interpreter.interpret(path))
            except Exception as exc:
                results.append(InterpreterResult(
                    interpreter=interpreter.name,
                    interpreter_version=interpreter.version,
                    recognized=False,
                    identity=None,
                    valid=False,
                    observations=InterpretationObservations(),
                    warnings=[],
                    errors=[f"{type(exc).__name__}: {str(exc)[:300]}"],
                ))

        first, second = results
        signals = []

        def compare(field: str, left: object, right: object) -> bool | None:
            if left is None or right is None:
                return None
            matches = left == right
            if not matches:
                signals.append(DisagreementSignal(
                    code=field,
                    interpreters=[first.interpreter, second.interpreter],
                    values={first.interpreter: left, second.interpreter: right},
                ))
            return matches

        agreement_fields = {
            "identity": compare("IDENTITY_DISAGREEMENT", first.identity, second.identity),
            "validity": compare("VALIDITY_DISAGREEMENT", first.valid, second.valid),
        }
        if family == "PDF":
            agreement_fields.update(
                page_count=compare("PAGE_COUNT_DISAGREEMENT", first.observations.page_count, second.observations.page_count),
                encrypted=compare("ENCRYPTION_STATE_DISAGREEMENT", first.observations.encrypted, second.observations.encrypted),
            )
        elif family == "ZIP":
            agreement_fields.update(
                entry_count=compare("ZIP_ENTRY_COUNT_DISAGREEMENT", first.observations.entry_count, second.observations.entry_count),
                total_uncompressed_size=compare("ZIP_UNCOMPRESSED_SIZE_DISAGREEMENT", first.observations.total_uncompressed_size, second.observations.total_uncompressed_size),
            )
        elif family == "PNG":
            left = first.observations
            right = second.observations
            if None not in (left.width, left.height, right.width, right.height):
                agreement_fields["image_dimensions"] = compare(
                    "IMAGE_DIMENSION_DISAGREEMENT",
                    f"{left.width}x{left.height}", f"{right.width}x{right.height}",
                )
        agreement = Agreement(**agreement_fields)
        result = InterpretationResult(
            artifact_id=artifact.artifact_id,
            sha256=artifact.sha256,
            artifact_family=family,
            interpreters=results,
            comparison=InterpretationComparison(
                interpreters_run=len(results),
                interpreters_recognized=sum(item.recognized for item in results),
                interpreters_valid=sum(item.valid for item in results),
                agreement=agreement,
            ),
            signals=signals,
        )
        self._results[artifact.artifact_id] = result
        return result
