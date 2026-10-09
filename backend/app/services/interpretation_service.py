from pathlib import Path
from uuid import UUID

from app.interpreters.base import Interpreter
from app.interpreters.pdf.pymupdf_interpreter import PyMuPDFInterpreter
from app.interpreters.pdf.pypdf_interpreter import PypdfInterpreter
from app.interpreters.png.pillow_interpreter import PillowInterpreter
from app.interpreters.png.pymupdf_interpreter import PyMuPDFPNGInterpreter
from app.interpreters.zip.stream_unzip_interpreter import StreamUnzipInterpreter
from app.interpreters.zip.zipfile_interpreter import ZipfileInterpreter
from app.interpreters.zip.name_report import comparable_zip_names
from app.schemas.artifact import ArtifactMetadata
from app.schemas.interpretation import (
    Agreement,
    ComparisonCoverage,
    DisagreementSignal,
    InterpretationComparison,
    InterpretationResult,
    InterpreterResult,
    InterpretationObservations,
    PropertyComparison,
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
        properties = []

        def not_comparable(
            property_name: str,
            signal_code: str,
            left: object,
            right: object,
            reason: str,
        ) -> None:
            properties.append(PropertyComparison(
                property_name=property_name,
                signal_code=signal_code,
                status="NOT_COMPARABLE",
                interpreters=[first.interpreter, second.interpreter],
                values={
                    first.interpreter: left,
                    second.interpreter: right,
                },
                reason=reason,
            ))

        def compare(
            property_name: str,
            signal_code: str,
            left: object,
            right: object,
            *,
            emit_signal: bool = True,
        ) -> bool | None:
            if left is None or right is None:
                not_comparable(
                    property_name,
                    signal_code,
                    left,
                    right,
                    "MISSING_OBSERVATION",
                )
                return None

            matches = left == right

            properties.append(PropertyComparison(
                property_name=property_name,
                signal_code=signal_code,
                status="AGREEMENT" if matches else "DISAGREEMENT",
                interpreters=[first.interpreter, second.interpreter],
                values={
                    first.interpreter: left,
                    second.interpreter: right,
                },
            ))

            # Only the historical fracture-bearing comparison vocabulary
            # produces legacy DisagreementSignal objects. New observational
            # comparisons must not manufacture Semantic Fractures.
            if not matches and emit_signal:
                signals.append(DisagreementSignal(
                    code=signal_code,
                    interpreters=[first.interpreter, second.interpreter],
                    values={
                        first.interpreter: left,
                        second.interpreter: right,
                    },
                ))

            return matches

        agreement_fields = {
            "identity": compare(
                "identity",
                "IDENTITY_DISAGREEMENT",
                first.identity,
                second.identity,
            ),
            "validity": compare(
                "validity",
                "VALIDITY_DISAGREEMENT",
                first.valid,
                second.valid,
            ),
        }

        if family == "PDF":
            agreement_fields.update(
                page_count=compare(
                    "page_count",
                    "PAGE_COUNT_DISAGREEMENT",
                    first.observations.page_count,
                    second.observations.page_count,
                ),
                encrypted=compare(
                    "encrypted",
                    "ENCRYPTION_STATE_DISAGREEMENT",
                    first.observations.encrypted,
                    second.observations.encrypted,
                ),
            )

            # Capability visibility is useful evidence intelligence but is
            # NOT automatically a Semantic Fracture. Different adapters may
            # expose different capability surfaces.
            compare(
                "javascript_action_count",
                "PDF_JAVASCRIPT_ACTION_COUNT_DIFFERENCE",
                first.observations.javascript_action_count,
                second.observations.javascript_action_count,
                emit_signal=False,
            )
            compare(
                "launch_action_count",
                "PDF_LAUNCH_ACTION_COUNT_DIFFERENCE",
                first.observations.launch_action_count,
                second.observations.launch_action_count,
                emit_signal=False,
            )
            compare(
                "richmedia_count",
                "PDF_RICHMEDIA_COUNT_DIFFERENCE",
                first.observations.richmedia_count,
                second.observations.richmedia_count,
                emit_signal=False,
            )

        elif family == "ZIP":
            agreement_fields.update(
                entry_count=compare(
                    "entry_count",
                    "ZIP_ENTRY_COUNT_DISAGREEMENT",
                    first.observations.entry_count,
                    second.observations.entry_count,
                ),
                total_uncompressed_size=compare(
                    "total_uncompressed_size",
                    "ZIP_UNCOMPRESSED_SIZE_DISAGREEMENT",
                    first.observations.total_uncompressed_size,
                    second.observations.total_uncompressed_size,
                ),
            )

            if comparable_zip_names(first.warnings, second.warnings):
                left_names = first.observations.entry_names
                right_names = second.observations.entry_names

                agreement_fields["entry_name_set"] = compare(
                    "entry_name_set",
                    "ZIP_ENTRY_NAME_SET_DISAGREEMENT",
                    sorted(set(left_names)) if left_names is not None else None,
                    sorted(set(right_names)) if right_names is not None else None,
                )

                agreement_fields["duplicate_entry_names"] = compare(
                    "duplicate_entry_names",
                    "ZIP_DUPLICATE_NAME_DISAGREEMENT",
                    first.observations.duplicate_entry_names,
                    second.observations.duplicate_entry_names,
                )
            else:
                agreement_fields["entry_name_set"] = None
                agreement_fields["duplicate_entry_names"] = None

                not_comparable(
                    "entry_name_set",
                    "ZIP_ENTRY_NAME_SET_DISAGREEMENT",
                    first.observations.entry_names,
                    second.observations.entry_names,
                    "INTERPRETER_NAME_REPORTS_NOT_COMPARABLE",
                )

                not_comparable(
                    "duplicate_entry_names",
                    "ZIP_DUPLICATE_NAME_DISAGREEMENT",
                    first.observations.duplicate_entry_names,
                    second.observations.duplicate_entry_names,
                    "INTERPRETER_NAME_REPORTS_NOT_COMPARABLE",
                )

            # Same rule as PDF capability observations: useful deterministic
            # comparison evidence, but not a new fracture signal.
            compare(
                "path_traversal_entry_count",
                "ZIP_PATH_TRAVERSAL_COUNT_DIFFERENCE",
                first.observations.path_traversal_entry_count,
                second.observations.path_traversal_entry_count,
                emit_signal=False,
            )
            compare(
                "absolute_path_entry_count",
                "ZIP_ABSOLUTE_PATH_COUNT_DIFFERENCE",
                first.observations.absolute_path_entry_count,
                second.observations.absolute_path_entry_count,
                emit_signal=False,
            )

        elif family == "PNG":
            left = first.observations
            right = second.observations

            left_dimensions = (
                f"{left.width}x{left.height}"
                if left.width is not None and left.height is not None
                else None
            )
            right_dimensions = (
                f"{right.width}x{right.height}"
                if right.width is not None and right.height is not None
                else None
            )

            agreement_fields["image_dimensions"] = compare(
                "image_dimensions",
                "IMAGE_DIMENSION_DISAGREEMENT",
                left_dimensions,
                right_dimensions,
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
                properties=properties,
                coverage=ComparisonCoverage(
                    total=len(properties),
                    agreement_count=sum(
                        item.status == "AGREEMENT"
                        for item in properties
                    ),
                    disagreement_count=sum(
                        item.status == "DISAGREEMENT"
                        for item in properties
                    ),
                    not_comparable_count=sum(
                        item.status == "NOT_COMPARABLE"
                        for item in properties
                    ),
                ),
            ),
            signals=signals,
        )
        self._results[artifact.artifact_id] = result
        return result
