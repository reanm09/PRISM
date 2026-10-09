"""Bounded raw-byte security precursors; never authoritative capability evidence."""

import re
from pathlib import Path

from app.schemas.fastscan import PDFSecurityPrecursors


MAX_PDF_SYNTAX_BYTES = 16 * 1024 * 1024
MAX_PDF_TOKENS = 200_000
MAX_PDF_DICTIONARIES = 20_000
MAX_PDF_DICTIONARY_DEPTH = 32
PDF_SPACE = b"\x00\x09\x0a\x0c\x0d\x20"
PDF_DELIMITERS = b"()<>[]{}/%"
ENDSTREAM = re.compile(rb"(?:\r\n|\r|\n)endstream(?=\s|$)")


class IncompletePDFSyntax(ValueError):
    pass


def _name(data: bytes) -> bytes:
    # PDF name escapes are # followed by exactly two hexadecimal digits.
    return re.sub(rb"#([0-9a-fA-F]{2})", lambda match: bytes.fromhex(match.group(1).decode("ascii")), data)


def _tokens(data: bytes):
    cursor = 0
    length = len(data)
    while cursor < length:
        char = data[cursor]
        if char in PDF_SPACE:
            cursor += 1
            continue
        if char == 0x25:  # % comment, including %%EOF
            while cursor < length and data[cursor] not in b"\r\n":
                cursor += 1
            continue
        if data.startswith(b"<<", cursor):
            cursor += 2
            yield "DICT_OPEN", b""
            continue
        if data.startswith(b">>", cursor):
            cursor += 2
            yield "DICT_CLOSE", b""
            continue
        if char == 0x28:  # Literal string with balanced, escaped parentheses.
            cursor += 1
            depth = 1
            while cursor < length and depth:
                current = data[cursor]
                if current == 0x5c:
                    cursor += 2
                    continue
                if current == 0x28:
                    depth += 1
                elif current == 0x29:
                    depth -= 1
                cursor += 1
            if depth:
                raise IncompletePDFSyntax("Unterminated PDF literal string")
            yield "OTHER", b""
            continue
        if char == 0x3c:  # Hex string; dictionary opener handled above.
            ending = data.find(b">", cursor + 1)
            if ending < 0:
                raise IncompletePDFSyntax("Unterminated PDF hex string")
            cursor = ending + 1
            yield "OTHER", b""
            continue
        if char == 0x2f:  # PDF name token.
            start = cursor + 1
            cursor = start
            while cursor < length and data[cursor] not in PDF_SPACE + PDF_DELIMITERS:
                cursor += 1
            yield "NAME", _name(data[start:cursor])
            continue
        if char in b"[]":
            cursor += 1
            yield ("ARRAY_OPEN" if char == 0x5b else "ARRAY_CLOSE"), b""
            continue
        if char in PDF_DELIMITERS:
            cursor += 1
            yield "OTHER", b""
            continue
        start = cursor
        while cursor < length and data[cursor] not in PDF_SPACE + PDF_DELIMITERS:
            cursor += 1
        word = data[start:cursor]
        if word == b"stream":
            # Stream bytes are not PDF object syntax. Skip bounded raw content
            # without decoding or interpreting it.
            if data.startswith(b"\r\n", cursor):
                cursor += 2
            elif cursor < length and data[cursor] in b"\r\n":
                cursor += 1
            else:
                raise IncompletePDFSyntax("Stream boundary unavailable")
            ending = ENDSTREAM.search(data, cursor)
            if ending is None:
                raise IncompletePDFSyntax("Endstream boundary unavailable")
            cursor = ending.end()
        yield "OTHER", word


def pdf_security_precursors(path: Path, size: int) -> PDFSecurityPrecursors:
    unavailable = PDFSecurityPrecursors(
        javascript_action_candidate_count=None, launch_action_candidate_count=None,
        richmedia_annotation_candidate_count=None, syntax_scan_complete=False,
    )
    if size > MAX_PDF_SYNTAX_BYTES:
        return unavailable
    with path.open("rb") as source:
        data = source.read(MAX_PDF_SYNTAX_BYTES + 1)
    if len(data) != size or not data.startswith(b"%PDF-"):
        return unavailable
    counts = {b"JavaScript": 0, b"Launch": 0, b"RichMedia": 0}
    stack: list[dict] = []
    array_depth = 0
    dictionaries = 0
    in_object = False
    preceding_numbers: list[bytes] = []
    try:
        for token_count, (kind, value) in enumerate(_tokens(data), 1):
            if token_count > MAX_PDF_TOKENS:
                raise IncompletePDFSyntax("PDF token cap reached")
            if kind == "OTHER" and value == b"obj":
                if len(preceding_numbers) != 2 or in_object:
                    raise IncompletePDFSyntax("PDF object boundary unavailable")
                in_object = True
            elif kind == "OTHER" and value == b"endobj":
                if not in_object or stack or array_depth:
                    raise IncompletePDFSyntax("Unbalanced PDF object")
                in_object = False
            if kind == "DICT_OPEN":
                dictionaries += 1
                if dictionaries > MAX_PDF_DICTIONARIES or len(stack) >= MAX_PDF_DICTIONARY_DEPTH:
                    raise IncompletePDFSyntax("PDF dictionary cap reached")
                if stack:
                    stack[-1]["pending"] = None
                stack.append({"pending": None, "array_depth": array_depth})
            elif kind == "DICT_CLOSE":
                if not stack:
                    raise IncompletePDFSyntax("Unbalanced PDF dictionary")
                stack.pop()
            elif kind == "ARRAY_OPEN":
                if stack:
                    stack[-1]["pending"] = None
                array_depth += 1
            elif kind == "ARRAY_CLOSE":
                if not array_depth:
                    raise IncompletePDFSyntax("Unbalanced PDF array")
                array_depth -= 1
            elif stack and stack[-1]["array_depth"] == array_depth:
                frame = stack[-1]
                if kind == "NAME":
                    key = frame["pending"]
                    if key is None:
                        frame["pending"] = value
                    else:
                        if in_object and ((key == b"S" and value in (b"JavaScript", b"Launch")) or (
                            key == b"Subtype" and value == b"RichMedia"
                        )):
                            counts[value] += 1
                        frame["pending"] = None
                else:
                    frame["pending"] = None
            if kind == "OTHER" and value.isdigit():
                preceding_numbers = (preceding_numbers + [value])[-2:]
            else:
                preceding_numbers = []
        if stack or array_depth or in_object:
            raise IncompletePDFSyntax("Unclosed PDF container")
    except IncompletePDFSyntax:
        return unavailable
    return PDFSecurityPrecursors(
        javascript_action_candidate_count=counts[b"JavaScript"],
        launch_action_candidate_count=counts[b"Launch"],
        richmedia_annotation_candidate_count=counts[b"RichMedia"],
        syntax_scan_complete=True,
    )


def zip_name_precursors(raw_name: bytes) -> tuple[bool, bool]:
    normalized = raw_name.replace(b"\\", b"/")
    absolute = normalized.startswith(b"/") or bool(re.match(rb"[A-Za-z]:/", normalized))
    depth = 0
    escaping = False
    for component in normalized.split(b"/"):
        if component in (b"", b"."):
            continue
        if component == b"..":
            if depth:
                depth -= 1
            else:
                escaping = True
        else:
            depth += 1
    return escaping, absolute
