import asyncio
import json
from pathlib import Path
from queue import Empty
import sys
import webbrowser

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.artifacts import analyze_artifact, artifact_service, fastscan_service, laya_triage_service
from app.schemas.sentinel import PublicWatchRoot, SentinelEvent, SentinelStatus
from app.services.sentinel_service import SentinelService
from app.services.quarantine_runtime import quarantine_service


router = APIRouter(prefix="/api/sentinel", tags=["sentinel"])


def _notify_quarantine(record):
    print(f"[PRISM SENTINEL] QUARANTINED: {record.original_name} | Trigger: {record.trigger} | Container: {Path(record.container_path).name}",
          file=sys.stderr, flush=True)
    runtime_path = artifact_service.config.artifact_storage.parent / "runtime.json"
    if runtime_path.exists():
        state = json.loads(runtime_path.read_text(encoding="utf-8"))
        port = state.get("frontend_port")
        if isinstance(port, int) and 1 <= port <= 65535:
            webbrowser.open(f"http://127.0.0.1:{port}/artifacts/{record.artifact_id}")


sentinel_service = SentinelService(
    artifact_service.config.artifact_storage.parent / "sentinel_config.json",
    artifact_service,
    lambda artifact: analyze_artifact(artifact.artifact_id),
    fastscan=fastscan_service, triage=laya_triage_service,
    quarantine=quarantine_service, notify_quarantine=_notify_quarantine,
)


@router.get("/status", response_model=SentinelStatus)
def sentinel_status() -> SentinelStatus:
    return sentinel_service.status()


@router.get("/watch-roots", response_model=list[PublicWatchRoot])
def watch_roots() -> list[PublicWatchRoot]:
    return sentinel_service.public_roots()


@router.get("/events/recent", response_model=list[SentinelEvent])
def recent_events() -> list[SentinelEvent]:
    return sentinel_service.recent()


@router.get("/events")
async def sentinel_events(request: Request) -> StreamingResponse:
    subscriber = sentinel_service.subscribe()

    async def stream():
        try:
            while not await request.is_disconnected():
                try:
                    event = await asyncio.to_thread(subscriber.get, True, 15)
                except Empty:
                    yield ": keepalive\n\n"
                    continue
                if event is None:
                    break
                data = json.dumps(event.model_dump(mode="json"), separators=(",", ":"))
                yield f"id: {event.event_id}\nevent: sentinel\ndata: {data}\n\n"
        finally:
            sentinel_service.unsubscribe(subscriber)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
