from importlib.metadata import version
from pathlib import Path

from stream_unzip import stream_unzip

from app.interpreters.zip.name_report import ZipNameReport
from app.schemas.interpretation import InterpreterResult, InterpretationObservations


class StreamUnzipInterpreter:
    name = "stream-unzip"
    version = version("stream-unzip")

    def __init__(self, max_uncompressed_bytes: int):
        self.max_uncompressed_bytes = max_uncompressed_bytes

    def interpret(self, path: Path) -> InterpreterResult:
        def chunks():
            with path.open("rb") as source:
                while chunk := source.read(65536):
                    yield chunk

        entry_count = 0
        total_size = 0
        directories = 0
        names = ZipNameReport()
        for name, _reported_size, contents in stream_unzip(chunks()):
            entry_count += 1
            directories += name.endswith(b"/")
            if name.isascii():
                logical_name = name.decode("ascii")
            else:
                names.encoding_uncertain = True
                try:
                    logical_name = name.decode("utf-8")
                except UnicodeDecodeError:
                    logical_name = name.decode("cp437")
            names.add(logical_name)
            for chunk in contents:
                total_size += len(chunk)
                if total_size > self.max_uncompressed_bytes:
                    raise ValueError("ZIP uncompressed content exceeds configured size limit")

        entry_names, duplicate_entry_names, warnings = names.finish()
        return InterpreterResult(
            interpreter=self.name, interpreter_version=self.version,
            recognized=True, identity="ZIP", valid=True,
            observations=InterpretationObservations(
                entry_count=entry_count,
                total_uncompressed_size=total_size,
                directory_entries=directories,
                encrypted_entries=None,
                entry_names=entry_names,
                duplicate_entry_names=duplicate_entry_names,
            ),
            warnings=warnings, errors=[],
        )
