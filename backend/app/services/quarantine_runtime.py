"""Shared local quarantine runtime.

This module owns the single QuarantineService instance used by
Sentinel, quarantine APIs, and read-only Evidence Intelligence.
"""

from pathlib import Path

from app.core.config import settings
from app.services.quarantine_service import QuarantineService


quarantine_service = QuarantineService(
    Path(__file__).resolve().parents[3] / "Quarantine",
    settings.artifact_storage.parent,
)
