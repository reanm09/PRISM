"""Loopback launcher for the existing PRISM web and API services."""

import argparse
import ctypes
import json
import os
import secrets
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser


BACKEND = Path(__file__).resolve().parents[1]
FRONTEND = BACKEND.parent
STATE = BACKEND / "storage" / "runtime.json"
SENTINEL_CONFIG = BACKEND / "storage" / "sentinel_config.json"
QUARANTINE_ROOT = FRONTEND / "Quarantine"
def _urls(state: dict) -> tuple[str, str]:
    return (f"http://127.0.0.1:{state.get('backend_port', 8000)}",
            f"http://127.0.0.1:{state.get('frontend_port', 3000)}")


def _creation_time(pid: int) -> int | None:
    if os.name != "nt":
        return None
    kernel = ctypes.windll.kernel32
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        created = ctypes.c_ulonglong()
        exited = ctypes.c_ulonglong()
        kernel_time = ctypes.c_ulonglong()
        user_time = ctypes.c_ulonglong()
        if not kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel_time), ctypes.byref(user_time)):
            return None
        exit_code = ctypes.c_ulong()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)) or exit_code.value != 259:
            return None
        return created.value
    finally:
        kernel.CloseHandle(handle)


def _owned(entry: dict | None) -> bool:
    return bool(entry and _creation_time(int(entry["pid"])) == entry["created"])


def _reachable(url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 300
    except (OSError, urllib.error.URLError):
        return False


def _load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def _save(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE.with_suffix(".tmp")
    temp.write_text(json.dumps(state), encoding="utf-8")
    temp.replace(STATE)


def _launch(name: str, command: list[str], cwd: Path, env: dict[str, str]) -> dict:
    log = (BACKEND / "storage" / f"{name}.log").open("ab")
    try:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
    finally:
        log.close()
    created = _creation_time(process.pid)
    if created is None:
        process.terminate()
        raise RuntimeError(f"Cannot verify ownership of {name} process")
    return {"pid": process.pid, "created": created}


def _stop_owned(entry: dict | None) -> bool:
    if not _owned(entry):
        return True
    subprocess.run(["taskkill", "/PID", str(entry["pid"]), "/T"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if _owned(entry):
        subprocess.run(["taskkill", "/PID", str(entry["pid"]), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if _owned(entry):
        # Some Windows installations deny taskkill even for a process this
        # launcher owns; Stop-Process can still terminate that exact PID.
        subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                        f"Stop-Process -Id {int(entry['pid'])} -Force -ErrorAction Stop"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return not _owned(entry)


def _request_backend_shutdown(state: dict) -> bool:
    entry = state.get("backend")
    if not _owned(entry):
        return True
    token = state.get("runtime_token")
    if not token:
        return False
    backend_url, _ = _urls(state)
    request = urllib.request.Request(f"{backend_url}/api/local/runtime/shutdown",
                                     data=b"", method="POST",
                                     headers={"X-Prism-Runtime-Token": token})
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            if response.status != 202:
                return False
    except (OSError, urllib.error.URLError):
        return False
    deadline = time.monotonic() + 5
    while _owned(entry) and time.monotonic() < deadline:
        time.sleep(0.1)
    return not _owned(entry)


def _wait(url: str, entry: dict, seconds: int = 45) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if _reachable(url):
            return True
        if not _owned(entry):
            break
        time.sleep(0.5)
    return False


def start() -> int:
    if os.name != "nt":
        print("The PRISM local launcher currently requires Windows.")
        return 1
    old = _load()
    if any(_owned(old.get(name)) for name in ("backend", "frontend")):
        print("PRISM is already running. Use 'prism status'.")
        return 1
    if old and STATE.exists():
        STATE.unlink()
    ports = next(((api, web) for api, web in ((8000, 3000), (8001, 3001))
                  if not _reachable(f"http://127.0.0.1:{api}/health")
                  and not _reachable(f"http://127.0.0.1:{web}")), None)
    if ports is None:
        print("PRISM loopback ports are occupied; no process was started.")
        return 1
    backend_port, frontend_port = ports
    backend_url, frontend_url = f"http://127.0.0.1:{backend_port}", f"http://127.0.0.1:{frontend_port}"
    npm = shutil.which("npm.cmd")
    node = shutil.which("node.exe")
    next_bin = FRONTEND / "node_modules" / "next" / "dist" / "bin" / "next"
    if not npm or not node or not next_bin.is_file():
        print("Install the existing frontend dependencies with 'npm ci' in E:\\Prism.")
        return 1
    try:
        import uvicorn  # noqa: F401
    except ImportError:
        print("Uvicorn is unavailable in this Python environment.")
        return 1
    STATE.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(STATE, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        if _load():
            print("Runtime metadata already exists. Use 'prism status' or 'prism stop'.")
            return 1
        STATE.unlink(missing_ok=True)
        return start()
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write("{}")
    state: dict = {"backend_port": backend_port, "frontend_port": frontend_port,
                   "runtime_token": secrets.token_urlsafe(32)}
    try:
        env = os.environ.copy()
        env["NEXT_PUBLIC_PRISM_API_URL"] = backend_url
        env["PRISM_LOCAL_MODE"] = "1"
        backend_env = env.copy()
        backend_env["PRISM_RUNTIME_TOKEN"] = state["runtime_token"]
        state["backend"] = _launch("backend", [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(backend_port)], BACKEND, backend_env)
        _save(state)
        if not _wait(f"{backend_url}/health", state["backend"]):
            raise RuntimeError("Backend did not become ready; see backend/storage/backend.log")
        with (BACKEND / "storage" / "frontend-build.log").open("ab") as build_log:
            build = subprocess.run([npm, "run", "build"], cwd=FRONTEND, env=env,
                                   stdout=build_log, stderr=subprocess.STDOUT, check=False)
        if build.returncode:
            raise RuntimeError("Frontend build failed; see backend/storage/frontend-build.log")
        state["frontend"] = _launch("frontend", [node, str(next_bin), "start", "--hostname", "127.0.0.1", "--port", str(frontend_port)], FRONTEND, env)
        _save(state)
        if not _wait(frontend_url, state["frontend"], 90):
            raise RuntimeError("Frontend did not become ready; see backend/storage/frontend.log")
    except Exception as exc:
        stopped = [_stop_owned(state.get("frontend")),
                   _request_backend_shutdown(state) or _stop_owned(state.get("backend"))]
        if all(stopped):
            STATE.unlink(missing_ok=True)
        print(f"PRISM startup failed: {exc}")
        if not all(stopped):
            print("A PRISM-owned process could not be stopped; runtime metadata was preserved.")
        return 1
    status()
    webbrowser.open(frontend_url)
    return 0


def status() -> int:
    state = _load()
    backend_url, frontend_url = _urls(state)
    backend = _owned(state.get("backend")) and _reachable(f"{backend_url}/health")
    frontend = _owned(state.get("frontend")) and _reachable(frontend_url)
    print("PRISM Local Runtime")
    print(f"Backend       {'READY' if backend else 'STOPPED'}")
    print(f"Frontend      {'READY' if frontend else 'STOPPED'}")
    if backend:
        try:
            with urllib.request.urlopen(f"{backend_url}/api/local/status", timeout=3) as response:
                details = json.load(response)
            for name in ("ollama", "laya", "rag", "lab"):
                print(f"{name.capitalize():<14}{details.get(name, 'UNKNOWN')}")
            with urllib.request.urlopen(f"{backend_url}/api/sentinel/status", timeout=3) as response:
                sentinel = json.load(response)
            state_label = "ACTIVE" if sentinel.get("running") else "OFF"
            print(f"Sentinel      {state_label} ({sentinel.get('watch_root_count', 0)} configured folders)")
            from app.services.quarantine_service import QuarantineService
            records = [item for item in QuarantineService(QUARANTINE_ROOT, BACKEND / "storage").list()
                       if item.status == "QUARANTINED"]
            print(f"Quarantine    {'ACTIVE' if records else 'EMPTY'} ({len(records)} artifacts)")
            if records:
                latest = records[-1]
                print(f"LATEST QUARANTINE\n{latest.original_name}\nContainment    {latest.status}\nTrigger        {latest.trigger}\nLaya prediction {latest.laya_prediction or '—'}\nLaya confidence {latest.laya_confidence if latest.laya_confidence is not None else '—'}\nDeterministic  {latest.verified_state or 'No deterministic verified state'}\nContainer      {Path(latest.container_path).name}\nTime           {latest.quarantined_at.isoformat()}")
        except (OSError, ValueError):
            print("Local status   UNAVAILABLE")
    else:
        print(f"Ollama        {'READY' if _reachable('http://127.0.0.1:11434/api/tags') else 'UNAVAILABLE'}")
    if frontend:
        print(f"Web UI: {frontend_url}")
    return 0 if backend and frontend else 1


def stop() -> int:
    state = _load()
    stopped = [_stop_owned(state.get("frontend")),
               _request_backend_shutdown(state) or _stop_owned(state.get("backend"))]
    if not all(stopped):
        print("Unable to stop every PRISM-owned process. Runtime metadata was preserved; retry 'prism stop'.")
        return 1
    STATE.unlink(missing_ok=True)
    print("PRISM-owned frontend and backend stopped. External Ollama was left running.")
    return 0


def watch_command(action: str, path: str | None = None, *, recursive: bool = False) -> int:
    from app.services.sentinel_service import change_root, load_config, save_config

    try:
        if action in ("add", "remove"):
            change_root(SENTINEL_CONFIG, path or "", add=action == "add", recursive=recursive)
        elif action == "defaults":
            for name in ("Downloads", "Desktop", "Documents"):
                candidate = Path.home() / name
                if candidate.is_dir():
                    change_root(SENTINEL_CONFIG, str(candidate), add=True)
        elif action in ("on", "off"):
            config = load_config(SENTINEL_CONFIG)
            save_config(SENTINEL_CONFIG, config.model_copy(update={"enabled": action == "on"}))
        config = load_config(SENTINEL_CONFIG)
    except (OSError, ValueError) as exc:
        print(f"Sentinel configuration failed: {exc}")
        return 1
    print(f"Sentinel {'ON' if config.enabled else 'OFF'}")
    for root in config.watch_roots:
        print(f"  {root.path} {'(recursive)' if root.recursive else '(this folder only)'}")
    return 0


def quarantine_command(action: str, quarantine_id: str | None = None) -> int:
    from uuid import UUID
    from app.services.quarantine_service import QuarantineError, QuarantineService

    service = QuarantineService(QUARANTINE_ROOT, BACKEND / "storage")
    try:
        if action == "list":
            for item in service.list():
                print(f"{item.quarantine_id}  {item.status}  {item.original_name}  {item.trigger}")
        else:
            record_id = UUID(quarantine_id or "")
            if action == "info":
                item = service.get(record_id)
            else:
                state = _load()
                backend_url, _ = _urls(state)
                if _owned(state.get("backend")) and _reachable(f"{backend_url}/health"):
                    request = urllib.request.Request(f"{backend_url}/api/quarantine/{record_id}/restore",
                                                     data=b"", method="POST")
                    try:
                        with urllib.request.urlopen(request, timeout=15):
                            pass
                    except urllib.error.HTTPError as exc:
                        raise QuarantineError(exc.read().decode("utf-8", errors="replace")) from exc
                    item = service.get(record_id)
                else:
                    item = service.restore(record_id)
            if item is None:
                raise QuarantineError("Quarantine record not found")
            print(f"{item.quarantine_id}  {item.status}  {item.original_name}\nTrigger: {item.trigger}\nDeterministic: {item.verified_state or 'No deterministic verified state'}\nContainer: {Path(item.container_path).name}\nSHA-256: {item.sha256}")
    except (ValueError, OSError, QuarantineError) as exc:
        print(f"Quarantine failed: {exc}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="prism")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("start", "status", "stop"):
        commands.add_parser(name)
    watch_parser = commands.add_parser("watch")
    watch_actions = watch_parser.add_subparsers(dest="action", required=True)
    for name in ("list", "on", "off", "defaults"):
        watch_actions.add_parser(name)
    for name in ("add", "remove"):
        command = watch_actions.add_parser(name)
        command.add_argument("path")
        if name == "add":
            command.add_argument("--recursive", action="store_true")
    quarantine_parser = commands.add_parser("quarantine")
    quarantine_actions = quarantine_parser.add_subparsers(dest="action", required=True)
    quarantine_actions.add_parser("list")
    for name in ("info", "restore"):
        quarantine_actions.add_parser(name).add_argument("quarantine_id")
    args = parser.parse_args()
    if args.command == "watch":
        return watch_command(args.action, getattr(args, "path", None),
                             recursive=getattr(args, "recursive", False))
    if args.command == "quarantine":
        return quarantine_command(args.action, getattr(args, "quarantine_id", None))
    return {"start": start, "status": status, "stop": stop}[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
