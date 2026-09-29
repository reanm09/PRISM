import platform
import zipfile
from pathlib import Path

from app.schemas.interpretation import InterpreterResult, InterpretationObservations


class ZipfileInterpreter:
    name = "zipfile"
    version = platform.python_version()

    def interpret(self, path: Path) -> InterpreterResult:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            observations = InterpretationObservations(
                entry_count=len(entries),
                total_uncompressed_size=sum(entry.file_size for entry in entries),
                directory_entries=sum(entry.is_dir() for entry in entries),
                encrypted_entries=sum(bool(entry.flag_bits & 1) for entry in entries),
            )
        return InterpreterResult(
            interpreter=self.name, interpreter_version=self.version,
            recognized=True, identity="ZIP", valid=True,
            observations=observations, warnings=[], errors=[],
        )
