from pathlib import Path

import pymupdf

from app.schemas.interpretation import InterpreterResult, PdfObservations


class PyMuPDFInterpreter:
    name = "pymupdf"
    version = pymupdf.VersionBind

    def interpret(self, path: Path) -> InterpreterResult:
        with pymupdf.open(path) as document:
            encrypted = bool(document.is_encrypted)
            metadata = document.metadata or {}
            observations = PdfObservations(
                page_count=None if encrypted else document.page_count,
                encrypted=encrypted,
                metadata_present=any(value for key, value in metadata.items() if key != "format"),
            )
        return InterpreterResult(
            interpreter=self.name, interpreter_version=self.version,
            recognized=True, identity="PDF", valid=True,
            observations=observations, warnings=[], errors=[],
        )
