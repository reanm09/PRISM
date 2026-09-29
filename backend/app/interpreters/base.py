from pathlib import Path
from typing import Protocol

from app.schemas.interpretation import InterpreterResult


class Interpreter(Protocol):
    name: str
    version: str

    def interpret(self, path: Path) -> InterpreterResult: ...
