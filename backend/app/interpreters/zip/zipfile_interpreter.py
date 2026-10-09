import platform
import zipfile
from pathlib import Path

from app.interpreters.zip.name_report import ZipNameReport
from app.interpreters.zip.path_observations import zip_path_hazards
from app.schemas.interpretation import InterpreterResult, InterpretationObservations


class ZipfileInterpreter:
    name = "zipfile"
    version = platform.python_version()

    def interpret(self, path: Path) -> InterpreterResult:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            names = ZipNameReport()
            traversal_count = 0
            absolute_count = 0
            for entry in entries:
                names.add(entry.filename)
                traversal, absolute = zip_path_hazards(entry.filename)
                traversal_count += traversal
                absolute_count += absolute
            entry_names, duplicate_entry_names, warnings = names.finish()
            observations = InterpretationObservations(
                entry_count=len(entries),
                total_uncompressed_size=sum(entry.file_size for entry in entries),
                directory_entries=sum(entry.is_dir() for entry in entries),
                encrypted_entries=sum(bool(entry.flag_bits & 1) for entry in entries),
                entry_names=entry_names,
                duplicate_entry_names=duplicate_entry_names,
                path_traversal_entry_count=traversal_count,
                absolute_path_entry_count=absolute_count,
            )
        return InterpreterResult(
            interpreter=self.name, interpreter_version=self.version,
            recognized=True, identity="ZIP", valid=True,
            observations=observations, warnings=warnings, errors=[],
        )
