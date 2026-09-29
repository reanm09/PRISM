from importlib.metadata import version
from pathlib import Path

from stream_unzip import stream_unzip

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
        for name, _reported_size, contents in stream_unzip(chunks()):
            entry_count += 1
            directories += name.endswith(b"/")
            for chunk in contents:
                total_size += len(chunk)
                if total_size > self.max_uncompressed_bytes:
                    raise ValueError("ZIP uncompressed content exceeds configured size limit")

        return InterpreterResult(
            interpreter=self.name, interpreter_version=self.version,
            recognized=True, identity="ZIP", valid=True,
            observations=InterpretationObservations(
                entry_count=entry_count,
                total_uncompressed_size=total_size,
                directory_entries=directories,
                encrypted_entries=None,
            ),
            warnings=[], errors=[],
        )
