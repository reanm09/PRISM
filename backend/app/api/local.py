from pathlib import Path
import hmac
import os
import signal
from threading import Timer

import httpx
from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import settings


router = APIRouter(prefix="/api/local", tags=["local"])


def _configured(path: Path) -> str:
    return "CONFIGURED" if path.exists() else "UNAVAILABLE"


@router.get("/status")
def local_status() -> dict[str, str]:
    try:
        response = httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=1.5)
        ollama = "READY" if response.is_success else "UNAVAILABLE"
    except httpx.HTTPError:
        ollama = "UNAVAILABLE"
    return {
        "backend": "READY",
        "ollama": ollama,
        "laya": _configured(settings.laya_model_path),
        "rag": _configured(settings.bge_model_path),
        "lab": "READY",
    }


@router.post("/runtime/shutdown", include_in_schema=False, status_code=202)
def shutdown_owned_runtime(request: Request, x_prism_runtime_token: str | None = Header(default=None)) -> dict[str, str]:
    expected = os.environ.get("PRISM_RUNTIME_TOKEN")
    if (not expected or not x_prism_runtime_token
            or request.client is None or request.client.host not in ("127.0.0.1", "::1")
            or not hmac.compare_digest(expected, x_prism_runtime_token)):
        raise HTTPException(status_code=404, detail="Not found")
    Timer(0.3, lambda: os.kill(os.getpid(), signal.SIGINT)).start()
    return {"status": "stopping"}
