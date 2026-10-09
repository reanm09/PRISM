from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


SentinelEventType = Literal[
    "ARTIFACT_DETECTED", "FILE_STABILIZING", "SCAN_STARTED", "ARTIFACT_INGESTED",
    "ANALYSIS_COMPLETED", "ALERT_RAISED", "SCAN_SKIPPED", "SCAN_FAILED",
    "QUARANTINE_STARTED", "QUARANTINE_COMPLETED", "QUARANTINE_FAILED", "QUARANTINE_RESTORED",
]


class WatchRoot(BaseModel):
    path: str
    recursive: bool = False
    enabled: bool = True


class SentinelConfig(BaseModel):
    enabled: bool = True
    watch_roots: list[WatchRoot] = Field(default_factory=list)


class SentinelEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: UUID
    timestamp: datetime
    event_type: SentinelEventType
    file_name: str | None = None
    artifact_id: UUID | None = None
    artifact_family: Literal["PDF", "ZIP", "PNG"] | None = None
    message: str
    verified_state: Literal["SUSPICIOUS", "FRACTURED"] | None = None
    routing_decision: Literal["PASS", "DEEP_SCAN", "PRISM_LAB"] | None = None
    laya_prediction: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    quarantine_id: UUID | None = None
    containment_state: Literal["QUARANTINED"] | None = None
    containment_trigger: Literal["LAYA_SUSPICIOUS", "DETERMINISTIC_SUSPICIOUS"] | None = None
    container_name: str | None = None
    laya_confidence: float | None = None


class SentinelStatus(BaseModel):
    enabled: bool
    running: bool
    watch_root_count: int
    supported_families: tuple[str, ...] = ("PDF", "ZIP", "PNG")


class PublicWatchRoot(BaseModel):
    root_id: str
    display_name: str
    recursive: bool
    enabled: bool
