from pathlib import Path

import pypdf

from app.schemas.interpretation import InterpreterResult, PdfObservations


class PypdfInterpreter:
    name = "pypdf"
    version = pypdf.__version__

    def interpret(self, path: Path) -> InterpreterResult:
        with path.open("rb") as source:
            reader = pypdf.PdfReader(source)
            encrypted = reader.is_encrypted
            metadata = reader.metadata
            observations = PdfObservations(
                page_count=None if encrypted else len(reader.pages),
                encrypted=encrypted,
                metadata_present=bool(metadata),
            )
        return InterpreterResult(
            interpreter=self.name, interpreter_version=self.version,
            recognized=True, identity="PDF", valid=True,
            observations=observations, warnings=[], errors=[],
        )
