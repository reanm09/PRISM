from pathlib import Path

import pymupdf

from app.schemas.interpretation import InterpreterResult, InterpretationObservations


class PyMuPDFPNGInterpreter:
    name = "pymupdf-png"
    version = pymupdf.VersionBind

    def interpret(self, path: Path) -> InterpreterResult:
        pixmap = pymupdf.Pixmap(str(path))
        return InterpreterResult(
            interpreter=self.name, interpreter_version=self.version,
            recognized=True, identity="PNG", valid=True,
            observations=InterpretationObservations(width=pixmap.width, height=pixmap.height),
            warnings=[], errors=[],
        )
