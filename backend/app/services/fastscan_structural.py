import re
import zlib
from pathlib import Path

from app.schemas.fastscan import (
    PDFStructuralFeatures, PNGStructuralFeatures, ZIPSecurityPrecursors, ZIPStructuralFeatures,
)
from app.services.fastscan_security import pdf_security_precursors, zip_name_precursors


PDF_TAIL_BYTES = 4096
ZIP_TAIL_BYTES = 65557  
MAX_ZIP_ENTRIES = 256
MAX_PNG_CHUNKS = 256
MAX_PNG_SCANNED_BYTES = 16 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PDF_EOF = re.compile(rb"%%EOF(?=\s|$)")
PDF_STARTXREF = re.compile(rb"(?:^|[\r\n])startxref\s+(\d+)(?=\s|$)")


def pdf_structure(path: Path, size: int) -> PDFStructuralFeatures:
    with path.open("rb") as source:
        source.seek(max(size - PDF_TAIL_BYTES, 0))
        tail = source.read(PDF_TAIL_BYTES)
    eof_markers = list(PDF_EOF.finditer(tail))
    last_eof = eof_markers[-1] if eof_markers else None
    terminal_eof = last_eof is not None and not tail[last_eof.end():].strip()
    declaration_region = tail[:last_eof.start()] if last_eof else tail
    declarations = list(PDF_STARTXREF.finditer(declaration_region))
    last_declaration = declarations[-1] if declarations else None
    offset = int(last_declaration.group(1)) if last_declaration else None
    return PDFStructuralFeatures(
        eof_marker_present=terminal_eof,
        startxref_present=last_declaration is not None,
        startxref_offset_in_bounds=(0 <= offset < size) if offset is not None else None,
        eof_marker_count=len(eof_markers),
        trailing_bytes_after_final_eof=(len(tail) - last_eof.end()) if last_eof else None,
    )


def zip_structure_with_security(path: Path, size: int) -> tuple[ZIPStructuralFeatures, ZIPSecurityPrecursors]:
    unavailable = ZIPStructuralFeatures(local_central_name_mismatch_count=None, central_directory_entry_count=None)
    security_unavailable = ZIPSecurityPrecursors(
        parent_traversal_entry_candidate_count=None,
        absolute_path_entry_candidate_count=None,
        directory_scan_complete=False,
    )
    with path.open("rb") as source:
        source.seek(max(size - ZIP_TAIL_BYTES, 0))
        tail = source.read(ZIP_TAIL_BYTES)
        end = tail.rfind(b"PK\x05\x06")
        if end < 0 or end + 22 > len(tail):
            return unavailable, security_unavailable
        eocd = tail[end:end + 22]
        disk = int.from_bytes(eocd[4:6], "little")
        cd_disk = int.from_bytes(eocd[6:8], "little")
        disk_entries = int.from_bytes(eocd[8:10], "little")
        entries = int.from_bytes(eocd[10:12], "little")
        cd_size = int.from_bytes(eocd[12:16], "little")
        cd_offset = int.from_bytes(eocd[16:20], "little")
        if (disk or cd_disk or disk_entries != entries or entries == 0xFFFF
                or cd_size == 0xFFFFFFFF or cd_offset == 0xFFFFFFFF):
            return unavailable, security_unavailable
        if entries > MAX_ZIP_ENTRIES:
            return ZIPStructuralFeatures(local_central_name_mismatch_count=None,
                                         central_directory_entry_count=entries), security_unavailable
        if cd_offset + cd_size > size:
            return unavailable, security_unavailable
        cursor = cd_offset
        mismatch_count = 0
        traversal_count = 0
        absolute_count = 0
        directory_end = cd_offset + cd_size
        for _ in range(entries):
            if cursor + 46 > directory_end:
                return unavailable, security_unavailable
            source.seek(cursor)
            central = source.read(46)
            if len(central) != 46 or central[:4] != b"PK\x01\x02":
                return unavailable, security_unavailable
            name_len = int.from_bytes(central[28:30], "little")
            extra_len = int.from_bytes(central[30:32], "little")
            comment_len = int.from_bytes(central[32:34], "little")
            local_offset = int.from_bytes(central[42:46], "little")
            next_cursor = cursor + 46 + name_len + extra_len + comment_len
            if next_cursor > directory_end or local_offset + 30 > size:
                return unavailable, security_unavailable
            central_name = source.read(name_len)
            if len(central_name) != name_len:
                return unavailable, security_unavailable
            traversal, absolute = zip_name_precursors(central_name)
            traversal_count += traversal
            absolute_count += absolute
            source.seek(local_offset)
            local = source.read(30)
            if len(local) != 30 or local[:4] != b"PK\x03\x04":
                return unavailable, security_unavailable
            local_name_len = int.from_bytes(local[26:28], "little")
            local_extra_len = int.from_bytes(local[28:30], "little")
            if local_offset + 30 + local_name_len + local_extra_len > size:
                return unavailable, security_unavailable
            local_name = source.read(local_name_len)
            if len(local_name) != local_name_len:
                return unavailable, security_unavailable
            mismatch_count += central_name != local_name
            cursor = next_cursor
        if cursor != directory_end:
            return unavailable, security_unavailable
    return ZIPStructuralFeatures(local_central_name_mismatch_count=mismatch_count,
                                 central_directory_entry_count=entries), ZIPSecurityPrecursors(
                                     parent_traversal_entry_candidate_count=traversal_count,
                                     absolute_path_entry_candidate_count=absolute_count,
                                     directory_scan_complete=True,
                                 )


def zip_structure(path: Path, size: int) -> ZIPStructuralFeatures:
    return zip_structure_with_security(path, size)[0]


def png_structure(path: Path, size: int) -> PNGStructuralFeatures:
    incomplete = PNGStructuralFeatures(iend_present=None, crc_error_count=None, structure_complete=None)
    with path.open("rb") as source:
        if source.read(8) != PNG_SIGNATURE:
            return incomplete
        cursor = 8
        crc_errors = 0
        for _ in range(MAX_PNG_CHUNKS):
            if cursor == size:
                return PNGStructuralFeatures(iend_present=False, crc_error_count=crc_errors,
                                             structure_complete=False)
            if cursor + 12 > size:
                return PNGStructuralFeatures(iend_present=False, crc_error_count=crc_errors,
                                             structure_complete=False)
            if cursor > MAX_PNG_SCANNED_BYTES:
                return incomplete
            source.seek(cursor)
            header = source.read(8)
            length = int.from_bytes(header[:4], "big")
            chunk_type = header[4:8]
            end = cursor + 12 + length
            if end > size:
                return PNGStructuralFeatures(iend_present=False, crc_error_count=crc_errors,
                                             structure_complete=False)
            if end > MAX_PNG_SCANNED_BYTES:
                return incomplete
            crc = zlib.crc32(chunk_type)
            remaining = length
            while remaining:
                data = source.read(min(remaining, 65536))
                if not data:
                    return PNGStructuralFeatures(iend_present=False, crc_error_count=crc_errors,
                                                 structure_complete=False)
                crc = zlib.crc32(data, crc)
                remaining -= len(data)
            stored_crc = source.read(4)
            if len(stored_crc) != 4:
                return PNGStructuralFeatures(iend_present=False, crc_error_count=crc_errors,
                                             structure_complete=False)
            crc_errors += crc != int.from_bytes(stored_crc, "big")
            if chunk_type == b"IEND":
                if length != 0:
                    return PNGStructuralFeatures(iend_present=False, crc_error_count=crc_errors,
                                                 structure_complete=False)
                return PNGStructuralFeatures(iend_present=True, crc_error_count=crc_errors,
                                             structure_complete=True)
            cursor = end
    return incomplete  


def scan_structure(path: Path, size: int, family: str):
    if family == "PDF":
        return pdf_structure(path, size)
    if family == "ZIP":
        return zip_structure(path, size)
    if family == "PNG":
        return png_structure(path, size)
    return None


def scan_structure_and_security(path: Path, size: int, family: str):
    if family == "PDF":
        return pdf_structure(path, size), pdf_security_precursors(path, size)
    if family == "ZIP":
        return zip_structure_with_security(path, size)
    if family == "PNG":
        return png_structure(path, size), None
    return None, None
