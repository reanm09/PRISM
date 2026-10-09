"""Bounded, opt-in filesystem observation; artifact truth stays with PRISM."""

import asyncio
from collections import OrderedDict, deque
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
import time
from uuid import uuid4

from fastapi import UploadFile
from watchfiles import Change, watch

from app.schemas.sentinel import PublicWatchRoot, SentinelConfig, SentinelEvent, SentinelStatus, WatchRoot


SUPPORTED_SUFFIXES = {".pdf", ".zip", ".png"}
QUARANTINE_ROOT = Path(__file__).resolve().parents[3] / "Quarantine"
MAX_HISTORY = 200
MAX_DEDUP = 512
MAX_PENDING = 256
MAX_SUBSCRIBER_QUEUE = 64


def load_config(path: Path) -> SentinelConfig:
    if not path.exists():
        return SentinelConfig()
    return SentinelConfig.model_validate_json(path.read_text(encoding="utf-8"))


def save_config(path: Path, config: SentinelConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)


def canonical_root(raw: str) -> Path:
    root = Path(raw).expanduser().resolve(strict=True)
    if not root.is_dir() or root == Path(root.anchor):
        raise ValueError("Watch root must be an existing folder below a drive root")
    if root == QUARANTINE_ROOT.resolve():
        raise ValueError("Quarantine cannot be a watch root")
    return root


def change_root(config_path: Path, raw: str, *, add: bool, recursive: bool = False) -> SentinelConfig:
    root = canonical_root(raw) if add else Path(raw).expanduser().resolve(strict=False)
    config = load_config(config_path)
    kept = [entry for entry in config.watch_roots if Path(entry.path) != root]
    if add:
        kept.append(WatchRoot(path=str(root), recursive=recursive))
    elif len(kept) == len(config.watch_roots):
        raise ValueError("Watch root is not configured")
    updated = config.model_copy(update={"watch_roots": kept})
    save_config(config_path, updated)
    return updated


def authorized_file(path: Path, root: WatchRoot) -> Path | None:
    try:
        base = canonical_root(root.path)
        resolved = path.resolve(strict=True)
        if resolved == QUARANTINE_ROOT.resolve() or QUARANTINE_ROOT.resolve() in resolved.parents:
            return None
        if resolved.name.lower().endswith((".prism", ".prism.tmp")):
            return None
        resolved.relative_to(base)
        if not root.recursive and resolved.parent != base:
            return None
        if path.is_symlink() or not resolved.is_file():
            return None
        return resolved
    except (OSError, ValueError):
        return None


class SentinelService:
    def __init__(self, config_path: Path, artifact_service, analyze, *, fastscan=None, triage=None,
                 quarantine=None, notify_quarantine=None, stable_interval: float = 0.6,
                 stable_checks: int = 2, max_stable_attempts: int = 8):
        self.config_path = config_path
        self.artifact_service = artifact_service
        self.analyze = analyze
        self.fastscan = fastscan
        self.triage = triage
        self.quarantine = quarantine
        self.notify_quarantine = notify_quarantine
        self.stable_interval = stable_interval
        self.stable_checks = stable_checks
        self.max_stable_attempts = max_stable_attempts
        self.history: deque[SentinelEvent] = deque(maxlen=MAX_HISTORY)
        self._subscribers: set[Queue] = set()
        self._lock = Lock()
        self._watcher_lock = Lock()
        self._pending: Queue[tuple[Path, WatchRoot]] = Queue(maxsize=MAX_PENDING)
        self._dedup: OrderedDict[str, str] = OrderedDict()
        self._stop = Event()
        self._watchers: dict[str, tuple[Event, Thread]] = {}
        self._threads: list[Thread] = []
        self.running = False
        self._config_signature: set[tuple[str, bool]] | None = None

    def status(self) -> SentinelStatus:
        config = load_config(self.config_path)
        with self._watcher_lock:
            watching = bool(self._watchers)
        return SentinelStatus(enabled=config.enabled, running=self.running and watching,
                              watch_root_count=sum(root.enabled for root in config.watch_roots))

    def public_roots(self) -> list[PublicWatchRoot]:
        return [PublicWatchRoot(root_id=hashlib.sha256(root.path.encode()).hexdigest()[:16],
                                display_name=Path(root.path).name, recursive=root.recursive, enabled=root.enabled)
                for root in load_config(self.config_path).watch_roots]

    def recent(self) -> list[SentinelEvent]:
        with self._lock:
            return list(reversed(self.history))

    def subscribe(self) -> Queue:
        subscriber: Queue = Queue(maxsize=MAX_SUBSCRIBER_QUEUE)
        with self._lock:
            self._subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: Queue) -> None:
        with self._lock:
            self._subscribers.discard(subscriber)

    def _emit(self, kind: str, message: str, **data) -> SentinelEvent:
        event = SentinelEvent(event_id=uuid4(), timestamp=datetime.now(timezone.utc),
                              event_type=kind, message=message, **data)
        with self._lock:
            self.history.append(event)
            for subscriber in self._subscribers:
                try:
                    subscriber.put_nowait(event)
                except Full:
                    try:
                        subscriber.get_nowait()
                    except Empty:
                        pass
                    subscriber.put_nowait(event)
        return event

    def start(self) -> None:
        if self.running:
            return
        load_config(self.config_path)  # Fail closed on invalid configuration.
        self._stop.clear()
        self.running = True
        self._threads = [Thread(target=self._supervise, name="prism-sentinel-supervisor", daemon=True),
                         Thread(target=self._consume, name="prism-sentinel-worker", daemon=True)]
        for thread in self._threads:
            thread.start()

    def stop(self) -> None:
        self._stop.set()
        self.running = False
        if self._threads:
            self._threads[0].join(timeout=5)
        with self._watcher_lock:
            watchers = list(self._watchers.values())
            self._watchers.clear()
        for event, _ in watchers:
            event.set()
        for _, thread in watchers:
            thread.join(timeout=3)
        self._watchers.clear()
        for thread in self._threads:
            thread.join(timeout=3)
        self._threads.clear()
        with self._lock:
            for subscriber in self._subscribers:
                try:
                    subscriber.put_nowait(None)
                except Full:
                    subscriber.get_nowait()
                    subscriber.put_nowait(None)
            self._subscribers.clear()

    def _supervise(self) -> None:
        while not self._stop.is_set():
            try:
                config = load_config(self.config_path)
                desired = {root.path: root for root in config.watch_roots if config.enabled and root.enabled
                           and Path(root.path).is_dir()}
            except (OSError, ValueError):
                desired = {}  # Invalid configuration withdraws every authorization.
            current = {(path, root.recursive) for path, root in desired.items()}
            with self._watcher_lock:
                if self._stop.is_set():
                    break
                if current != self._config_signature:
                    for event, thread in self._watchers.values():
                        event.set()
                        thread.join(timeout=3)
                    self._watchers.clear()
                    for path, root in desired.items():
                        event = Event()
                        thread = Thread(target=self._watch, args=(root, event), daemon=True)
                        self._watchers[path] = (event, thread)
                        thread.start()
                    self._config_signature = current
            self._stop.wait(0.5)

    def _watch(self, root: WatchRoot, stop: Event) -> None:
        try:
            for changes in watch(root.path, recursive=root.recursive, stop_event=stop, debounce=500):
                if stop.is_set() or self._stop.is_set():
                    break
                for change, raw in changes:
                    if change not in (Change.added, Change.modified):
                        continue
                    try:
                        self._pending.put_nowait((Path(raw), root))
                    except Full:
                        self._emit("SCAN_SKIPPED", "Sentinel queue is full; event skipped", file_name=Path(raw).name)
        except OSError:
            self._emit("SCAN_FAILED", "Watch root became unavailable", file_name=Path(root.path).name)

    def _consume(self) -> None:
        while not self._stop.is_set():
            try:
                path, root = self._pending.get(timeout=0.5)
            except Empty:
                continue
            try:
                self.process(path, root)
            except Exception:
                self._emit("SCAN_FAILED", "Sentinel could not process filesystem event", file_name=path.name)
            finally:
                self._pending.task_done()

    def _stable(self, path: Path, root: WatchRoot) -> Path | None:
        previous = None
        matches = 0
        for _ in range(self.max_stable_attempts):
            if self._stop.is_set():
                return None
            resolved = authorized_file(path, root)
            if resolved is None:
                return None
            try:
                stat = resolved.stat()
            except OSError:
                return None
            fingerprint = (stat.st_size, stat.st_mtime_ns)
            if fingerprint == previous:
                matches += 1
                if matches >= self.stable_checks:
                    return resolved
            else:
                previous, matches = fingerprint, 0
            self._stop.wait(self.stable_interval)
        return None

    def process(self, path: Path, root: WatchRoot) -> None:
        name = path.name
        config = load_config(self.config_path)
        if not config.enabled or root.path not in {item.path for item in config.watch_roots if item.enabled}:
            return
        if authorized_file(path, root) is None:
            return
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            self._emit("SCAN_SKIPPED", "Unsupported file extension", file_name=name)
            return
        self._emit("ARTIFACT_DETECTED", "Filesystem change detected", file_name=name)
        self._emit("FILE_STABILIZING", "Waiting for file writes to finish", file_name=name)
        stable = self._stable(path, root)
        if stable is None:
            self._emit("SCAN_SKIPPED", "File did not stabilize or left authorized root", file_name=name)
            return
        try:
            if stable.stat().st_size > self.artifact_service.config.max_upload_bytes:
                self._emit("SCAN_SKIPPED", "File exceeds upload limit", file_name=name)
                return
            digest = hashlib.sha256()
            with stable.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
            content_hash = digest.hexdigest()
            key = str(stable)
            if self._dedup.get(key) == content_hash:
                return
            if authorized_file(path, root) != stable:
                raise OSError("File moved outside authorized root")
            self._emit("SCAN_STARTED", "PRISM analysis started", file_name=name)
            with stable.open("rb") as source:
                metadata = asyncio.run(self.artifact_service.ingest(UploadFile(file=source, filename=name)))
            if metadata.sha256 != content_hash:
                raise OSError("File changed while being ingested")
            self._emit("ARTIFACT_INGESTED", "Artifact ingested", file_name=name,
                       artifact_id=metadata.artifact_id)
            prior = None
            contained = None
            if self.fastscan is not None and self.triage is not None:
                scan = self.fastscan.scan(metadata)
                prior = self.triage.predict(metadata, scan)
                if prior.predicted_state == "SUSPICIOUS":
                    contained = self._contain(stable, metadata, "LAYA_SUSPICIOUS", prior, None, [])
            result = self.analyze(metadata)
            if result.verified_state == "SUSPICIOUS" and contained is None:
                contained = self._contain(stable, metadata, "DETERMINISTIC_SUSPICIOUS",
                                          result.triage, result.verified_state, result.reason_codes)
            elif contained is not None:
                self.quarantine.update_evidence(contained.quarantine_id, result.verified_state, result.reason_codes)
            family = result.triage.model_input.observed_identity
            if family not in ("PDF", "ZIP", "PNG"):
                raise ValueError("Unsupported observed artifact family")
            self._dedup[key] = content_hash
            self._dedup.move_to_end(key)
            if len(self._dedup) > MAX_DEDUP:
                self._dedup.popitem(last=False)
            data = dict(file_name=name, artifact_id=metadata.artifact_id, artifact_family=family,
                        verified_state=result.verified_state, routing_decision=result.routing_decision,
                        laya_prediction=result.triage.predicted_state, reason_codes=result.reason_codes)
            self._emit("ANALYSIS_COMPLETED", "PRISM analysis completed", **data)
            if result.routing_decision == "PRISM_LAB" or result.verified_state:
                self._emit("ALERT_RAISED", "Deeper investigation available", **data)
        except Exception as exc:
            self._emit("SCAN_FAILED", f"PRISM analysis failed: {type(exc).__name__}", file_name=name)

    def _contain(self, source, metadata, trigger, triage, verified_state, reason_codes):
        if self.quarantine is None:
            raise RuntimeError("Quarantine service unavailable")
        self._emit("QUARANTINE_STARTED", "Containment started", file_name=source.name,
                   artifact_id=metadata.artifact_id, containment_trigger=trigger,
                   verified_state=verified_state)
        try:
            record = self.quarantine.quarantine(
                source, metadata, trigger=trigger, laya_prediction=triage.predicted_state,
                laya_confidence=triage.answer_confidence, verified_state=verified_state,
                reason_codes=reason_codes,
            )
        except Exception as exc:
            self._emit("QUARANTINE_FAILED", f"Containment failed: {type(exc).__name__}",
                       file_name=source.name, artifact_id=metadata.artifact_id,
                       containment_trigger=trigger, verified_state=verified_state)
            return None
        self._emit("QUARANTINE_COMPLETED", "Encrypted precautionary containment completed" if trigger == "LAYA_SUSPICIOUS" else "Encrypted deterministic containment completed",
                   file_name=source.name, artifact_id=metadata.artifact_id,
                   quarantine_id=record.quarantine_id, containment_state="QUARANTINED",
                   containment_trigger=trigger, container_name=Path(record.container_path).name,
                   laya_prediction=triage.predicted_state, laya_confidence=triage.answer_confidence,
                   verified_state=verified_state, reason_codes=reason_codes)
        if self.notify_quarantine:
            try:
                self.notify_quarantine(record)
            except Exception:
                pass
        return record
