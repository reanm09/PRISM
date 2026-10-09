import httpx

from app.core.config import Settings, settings
from app.services.rag.models import RagModelError


class OllamaGenerator:
    def __init__(self, base_url: str, model: str, *, client: httpx.Client | None = None,
                 config: Settings = settings):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.num_ctx = config.ollama_num_ctx
        self.client = client or httpx.Client(timeout=45.0, trust_env=False)

    def generate(
        self,
        system: str,
        user: str,
        *,
        format_json: bool | dict = False,
    ) -> str:
        structured = bool(format_json)

        if isinstance(format_json, dict):
            output_format = format_json
        elif format_json:
            output_format = "json"
        else:
            output_format = None

        try:
            response = self.client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    **(
                        {"format": output_format}
                        if output_format is not None
                        else {}
                    ),
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "options": {
                        "temperature": 0,
                        "num_predict": 1024 if structured else 160,
                        "num_ctx": self.num_ctx,
                    },
                },
                timeout=90.0 if structured else 45.0,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            raise RagModelError("Ollama did not respond within the request timeout") from exc
        except httpx.HTTPStatusError as exc:
            raise RagModelError(f"Ollama request failed (HTTP {exc.response.status_code})") from exc
        except httpx.RequestError as exc:
            raise RagModelError(f"Ollama is unavailable at {self.base_url}") from exc
        except ValueError as exc:
            raise RagModelError("Ollama returned invalid JSON") from exc
        message = payload.get("message") if isinstance(payload, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise RagModelError("Ollama returned no answer content")
        return content.strip()
