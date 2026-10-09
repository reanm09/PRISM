from collections import Counter


MAX_REPORTED_ZIP_ENTRY_NAMES = 256
MAX_REPORTED_ZIP_NAME_CHARS = 8192
TRUNCATED_WARNING = "ZIP_ENTRY_NAME_REPORT_TRUNCATED"
ENCODING_WARNING = "ZIP_ENTRY_NAME_ENCODING_UNCERTAIN"


class ZipNameReport:
    def __init__(self):
        self.names: list[str] = []
        self._characters = 0
        self.truncated = False
        self.encoding_uncertain = False

    def add(self, name: str) -> None:
        if self.truncated:
            return
        if len(self.names) >= MAX_REPORTED_ZIP_ENTRY_NAMES or self._characters + len(name) > MAX_REPORTED_ZIP_NAME_CHARS:
            self.truncated = True
            return
        self.names.append(name)
        self._characters += len(name)

    def finish(self) -> tuple[list[str], list[str] | None, list[str]]:
        warnings = []
        if self.truncated:
            warnings.append(TRUNCATED_WARNING)
        if self.encoding_uncertain:
            warnings.append(ENCODING_WARNING)
        duplicates = None if self.truncated else sorted(
            name for name, count in Counter(self.names).items() if count > 1
        )
        return self.names, duplicates, warnings


def comparable_zip_names(left_warnings: list[str], right_warnings: list[str]) -> bool:
    incomplete = {TRUNCATED_WARNING, ENCODING_WARNING}
    return not (incomplete.intersection(left_warnings) or incomplete.intersection(right_warnings))
