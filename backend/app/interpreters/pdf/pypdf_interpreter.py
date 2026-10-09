from pathlib import Path

import pypdf

from app.interpreters.pdf.structural_observations import INCOMPLETE_WARNING, inspect_pdf_structure
from app.schemas.interpretation import InterpreterResult, PdfObservations


class PypdfInterpreter:
    name = "pypdf"
    version = pypdf.__version__

    def interpret(self, path: Path) -> InterpreterResult:
        with path.open("rb") as source:
            reader = pypdf.PdfReader(source)
            encrypted = reader.is_encrypted
            metadata = reader.metadata
            try:
                security_counts, warnings = inspect_pdf_structure(reader)
            except Exception:
                security_counts, warnings = (None, None, None), [INCOMPLETE_WARNING]
            observations = PdfObservations(
                page_count=None if encrypted else len(reader.pages),
                encrypted=encrypted,
                metadata_present=bool(metadata),
                javascript_action_count=security_counts[0],
                launch_action_count=security_counts[1],
                richmedia_count=security_counts[2],
            )
        return InterpreterResult(
            interpreter=self.name, interpreter_version=self.version,
            recognized=True, identity="PDF", valid=True,
            observations=observations, warnings=warnings, errors=[],
        )
