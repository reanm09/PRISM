from importlib.metadata import version
from pathlib import Path

from PIL import Image

from app.schemas.interpretation import InterpreterResult, InterpretationObservations


class PillowInterpreter:
    name = "pillow"
    version = version("Pillow")

    def interpret(self, path: Path) -> InterpreterResult:
        with Image.open(path) as image:
            if image.format != "PNG":
                raise ValueError("Pillow did not recognize PNG")
            width, height = image.size
            mode = image.mode
            frame_count = getattr(image, "n_frames", None)
            image.verify()
        return InterpreterResult(
            interpreter=self.name, interpreter_version=self.version,
            recognized=True, identity="PNG", valid=True,
            observations=InterpretationObservations(
                width=width, height=height, color_mode=mode, frame_count=frame_count,
            ),
            warnings=[], errors=[],
        )
