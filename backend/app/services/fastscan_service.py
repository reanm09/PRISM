import hashlib
import math
from collections import Counter
from pathlib import Path
from uuid import UUID

from app.schemas.artifact import ArtifactMetadata
from app.schemas.fastscan import (
    ExtensionConsistency,
    FastScanResult,
    FastScanSignal,
    HeaderEvidence,
    IntegrityEvidence,
    ObservedIdentity,
    Statistics,
)
from app.services.fastscan_structural import scan_structure_and_security


IDENTITIES = {
    "PDF": ("application/pdf", "PDF document"),
    "ZIP": ("application/zip", "ZIP archive"),
    "PNG": ("image/png", "PNG image"),
    "JPEG": ("image/jpeg", "JPEG image"),
    "PE": ("application/vnd.microsoft.portable-executable", "Windows PE executable"),
    "ELF": ("application/x-elf", "ELF executable or shared object"),
    "UNKNOWN": ("application/octet-stream", "Unknown file signature"),
}
EXTENSION_TYPES = {
    ".pdf": "PDF",
    ".zip": "ZIP",
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".exe": "PE",
    ".dll": "PE",
    ".elf": "ELF",
}


PDF_HEADER_SEARCH_BYTES = 1024


def detect_type(header: bytes) -> str:
    # Acrobat-compatible PDF recovery:
    # real-world PDF consumers may accept %PDF- anywhere within
    # the first 1024 bytes rather than requiring byte offset zero.
    if b"%PDF-" in header[:PDF_HEADER_SEARCH_BYTES]:
        return "PDF"

    if header.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        return "ZIP"

    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"

    if header.startswith(b"\xff\xd8\xff"):
        return "JPEG"

    if header.startswith(b"\x7fELF"):
        return "ELF"

    if header.startswith(b"MZ") and len(header) >= 64:
        pe_offset = int.from_bytes(header[60:64], "little")
        if (
            pe_offset <= len(header) - 4
            and header[pe_offset:pe_offset + 4] == b"PE\0\0"
        ):
            return "PE"

    return "UNKNOWN"


class FastScanService:
    def __init__(self, storage: Path):
        self.storage = storage
        self._results: dict[UUID, FastScanResult] = {}

    def get(self, artifact_id: UUID) -> FastScanResult | None:
        return self._results.get(artifact_id)

    def scan(self, artifact: ArtifactMetadata) -> FastScanResult:
        path = self.storage / str(artifact.artifact_id)
        counts: Counter[int] = Counter()
        digest = hashlib.sha256()
        size = 0
        header = b""
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                if not header:
                    header = chunk[:4096]
                counts.update(chunk)
                digest.update(chunk)
                size += len(chunk)

        detected_type = detect_type(header)
        mime, description = IDENTITIES[detected_type]
        expected_type = EXTENSION_TYPES.get(artifact.claimed_extension.lower())
        matches = None if detected_type == "UNKNOWN" or not artifact.claimed_extension else expected_type == detected_type
        entropy = -sum((n / size) * math.log2(n / size) for n in counts.values()) if size else 0.0
        hash_matches = digest.hexdigest() == artifact.sha256
        signals = []

        pdf_header_offset = header[:PDF_HEADER_SEARCH_BYTES].find(b"%PDF-")
        if detected_type == "PDF" and pdf_header_offset > 0:
            signals.append(FastScanSignal(
                code="PDF_HEADER_NOT_AT_BYTE_ZERO",
                severity="WARNING",
                message=(
                    "PDF header was recovered within the first 1024 bytes "
                    "but did not begin at byte zero."
                ),
            ))

        if detected_type == "UNKNOWN":
            signals.append(FastScanSignal(
                code="UNKNOWN_FILE_TYPE", severity="INFO",
                message="No supported file signature was observed.",
            ))
        if matches is False:
            signals.append(FastScanSignal(
                code="EXTENSION_TYPE_MISMATCH", severity="WARNING",
                message=f"Claimed extension {artifact.claimed_extension} differs from byte-observed {detected_type} identity.",
            ))
        if not hash_matches:
            signals.append(FastScanSignal(
                code="ARTIFACT_HASH_MISMATCH", severity="ERROR",
                message="Stored artifact SHA-256 differs from the ingestion hash.",
            ))

        structural, security_precursors = scan_structure_and_security(path, size, detected_type)
        result = FastScanResult(
            artifact_id=artifact.artifact_id,
            sha256=digest.hexdigest(),
            size_bytes=size,
            claimed_extension=artifact.claimed_extension,
            observed=ObservedIdentity(detected_type=detected_type, detected_mime=mime, magic_description=description),
            consistency=ExtensionConsistency(extension_matches_observed=matches),
            statistics=Statistics(entropy=round(entropy, 4)),
            header=HeaderEvidence(first_bytes_hex=header[:32].hex()),
            integrity=IntegrityEvidence(sha256_matches_ingestion=hash_matches),
            signals=signals,
            structural_features=structural,
            pretriage_security_features=security_precursors,
        )
        self._results[artifact.artifact_id] = result
        return result
