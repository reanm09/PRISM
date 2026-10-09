"""Local, authenticated containment of files already snapshotted by PRISM."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from threading import Lock
from uuid import UUID, uuid4

from Crypto.Cipher import AES

from app.schemas.quarantine import QuarantineRecord


class QuarantineError(RuntimeError):
    pass


class _Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def _blob(data: bytes):
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    return _Blob(len(data), buffer), buffer


def _dpapi(data: bytes, *, protect: bool) -> bytes:
    if os.name != "nt":
        raise QuarantineError("Windows DPAPI is required for quarantine keys")
    source, buffer = _blob(data)
    result = _Blob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    method = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    method.argtypes = ([ctypes.POINTER(_Blob), wintypes.LPCWSTR, ctypes.POINTER(_Blob),
                        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
                       if protect else [ctypes.POINTER(_Blob), ctypes.POINTER(wintypes.LPWSTR),
                                        ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p,
                                        wintypes.DWORD, ctypes.POINTER(_Blob)])
    method.restype = wintypes.BOOL
    description = "PRISM quarantine key" if protect else None
    if not method(ctypes.byref(source), description, None, None, None, 0x1, ctypes.byref(result)):
        raise QuarantineError(f"Windows DPAPI failed: {ctypes.get_last_error()}")
    try:
        return ctypes.string_at(result.data, result.size)
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.cast(result.data, ctypes.c_void_p))


class QuarantineService:
    def __init__(self, root: Path, storage: Path):
        self.root = root
        self.registry_path = storage / "quarantine_registry.json"
        self.key_path = storage / "quarantine_key.dpapi"
        self._lock = Lock()

    def _key(self) -> bytes:
        if not self.key_path.exists():
            self.key_path.parent.mkdir(parents=True, exist_ok=True)
            protected = _dpapi(os.urandom(32), protect=True)
            try:
                with self.key_path.open("xb") as stream:
                    stream.write(protected)
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileExistsError:
                pass
        key = _dpapi(self.key_path.read_bytes(), protect=False)
        if len(key) != 32:
            raise QuarantineError("Invalid quarantine key")
        return key

    def _records(self) -> list[QuarantineRecord]:
        if not self.registry_path.exists():
            return []
        return [QuarantineRecord.model_validate(item) for item in json.loads(self.registry_path.read_text(encoding="utf-8"))]

    def _save(self, records: list[QuarantineRecord]) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.registry_path.with_suffix(".tmp")
        with temp.open("w", encoding="utf-8") as stream:
            json.dump([item.model_dump(mode="json") for item in records], stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(self.registry_path)

    def list(self) -> list[QuarantineRecord]:
        with self._lock:
            return self._records()

    def get(self, quarantine_id: UUID) -> QuarantineRecord | None:
        return next((item for item in self.list() if item.quarantine_id == quarantine_id), None)

    def update_evidence(self, quarantine_id: UUID, verified_state: str | None,
                        reason_codes: list[str]) -> QuarantineRecord:
        with self._lock:
            records = self._records()
            for index, item in enumerate(records):
                if item.quarantine_id == quarantine_id:
                    records[index] = item.model_copy(update={"verified_state": verified_state,
                                                             "reason_codes": reason_codes})
                    self._save(records)
                    return records[index]
        raise QuarantineError("Quarantine record not found")

    def for_artifact(self, artifact_id: UUID) -> QuarantineRecord | None:
        return next((item for item in reversed(self.list()) if item.artifact_id == artifact_id), None)

    def _open(self, container: Path) -> tuple[dict, bytes]:
        packed = json.loads(container.read_text(encoding="utf-8"))
        if packed.get("version") != 1:
            raise QuarantineError("Unsupported quarantine format")
        import base64
        nonce = base64.b64decode(packed["nonce"], validate=True)
        ciphertext = base64.b64decode(packed["ciphertext"], validate=True)
        tag = base64.b64decode(packed["tag"], validate=True)
        cipher = AES.new(self._key(), AES.MODE_GCM, nonce=nonce)
        plain = cipher.decrypt_and_verify(ciphertext, tag)
        payload = json.loads(plain)
        import base64 as b64
        data = b64.b64decode(payload["bytes"], validate=True)
        if hashlib.sha256(data).hexdigest() != payload["sha256"]:
            raise QuarantineError("Container SHA-256 mismatch")
        return payload, data

    def quarantine(self, source: Path, artifact, *, trigger: str, laya_prediction: str | None,
                   laya_confidence: float | None, verified_state: str | None,
                   reason_codes: list[str]) -> QuarantineRecord:
        import base64
        with self._lock:
            if not source.is_file() or source.is_symlink():
                raise QuarantineError("Source is missing or not a regular file")
            data = source.read_bytes()
            if hashlib.sha256(data).hexdigest() != artifact.sha256:
                raise QuarantineError("Source changed since ingestion; reanalysis required")
            records = self._records()
            self.root.mkdir(parents=True, exist_ok=True)
            name = source.name
            final = self.root / f"{name}.prism"
            if final.exists():
                final = self.root / f"{name}.{artifact.sha256[:12]}.prism"
            if final.exists():
                raise QuarantineError("Quarantine container already exists")
            temporary = final.with_name(final.name + ".tmp")
            if temporary.exists():
                raise QuarantineError("Quarantine transaction already exists")
            when = datetime.now(timezone.utc)
            payload = {"version": 1, "artifact_id": str(artifact.artifact_id), "original_name": name,
                       "sha256": artifact.sha256, "timestamp": when.isoformat(), "trigger": trigger,
                       "laya_prediction": laya_prediction, "laya_confidence": laya_confidence,
                       "verified_state": verified_state, "reason_codes": reason_codes,
                       "bytes": base64.b64encode(data).decode("ascii")}
            cipher = AES.new(self._key(), AES.MODE_GCM)
            ciphertext, tag = cipher.encrypt_and_digest(json.dumps(payload, sort_keys=True).encode("utf-8"))
            packed = {"version": 1, "nonce": base64.b64encode(cipher.nonce).decode("ascii"),
                      "tag": base64.b64encode(tag).decode("ascii"),
                      "ciphertext": base64.b64encode(ciphertext).decode("ascii")}
            try:
                with temporary.open("x", encoding="utf-8") as stream:
                    json.dump(packed, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
                checked, opened = self._open(temporary)
                if checked["sha256"] != artifact.sha256 or opened != data:
                    raise QuarantineError("Container verification failed")
                if final.exists() or hashlib.sha256(source.read_bytes()).hexdigest() != artifact.sha256:
                    raise QuarantineError("Destination occupied or source changed during containment")
                temporary.rename(final)
                record = QuarantineRecord(quarantine_id=uuid4(), artifact_id=artifact.artifact_id,
                                          original_path=str(source), container_path=str(final), original_name=name,
                                          sha256=artifact.sha256, trigger=trigger, laya_prediction=laya_prediction,
                                          laya_confidence=laya_confidence, verified_state=verified_state,
                                          reason_codes=reason_codes, quarantined_at=when)
                records.append(record)
                self._save(records)
                try:
                    if hashlib.sha256(source.read_bytes()).hexdigest() != artifact.sha256:
                        raise QuarantineError("Source changed before removal; reanalysis required")
                    source.unlink()
                except Exception:
                    records.pop()
                    self._save(records)
                    final.unlink(missing_ok=True)
                    raise
                return record
            finally:
                temporary.unlink(missing_ok=True)

    def restore(self, quarantine_id: UUID) -> QuarantineRecord:
        with self._lock:
            records = self._records()
            index = next((i for i, item in enumerate(records) if item.quarantine_id == quarantine_id), None)
            if index is None or records[index].status != "QUARANTINED":
                raise QuarantineError("Active quarantine record not found")
            record = records[index]
            destination = Path(record.original_path)
            if destination.exists() or destination.is_symlink():
                raise QuarantineError("Original destination is occupied")
            payload, data = self._open(Path(record.container_path))
            if (payload["sha256"] != record.sha256
                    or payload["artifact_id"] != str(record.artifact_id)
                    or payload["original_name"] != record.original_name
                    or payload["trigger"] != record.trigger
                    or hashlib.sha256(data).hexdigest() != record.sha256):
                raise QuarantineError("Restored SHA-256 mismatch")
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(destination.name + ".prism-restore-tmp")
            try:
                with temporary.open("xb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                if destination.exists():
                    raise QuarantineError("Original destination became occupied")
                temporary.rename(destination)
            finally:
                temporary.unlink(missing_ok=True)
            records[index] = record.model_copy(update={"status": "RESTORED", "restored_at": datetime.now(timezone.utc)})
            self._save(records)
            return records[index]
