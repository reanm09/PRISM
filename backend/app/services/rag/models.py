import hashlib
import threading
from pathlib import Path


class RagModelError(RuntimeError):
    pass


class BGEEmbedder:
    """Local BGE-M3 dense embeddings using its configured CLS pooling."""

    def __init__(self, path: Path):
        self.path = path
        self.model_id = str(path.resolve())
        self.dimension = 1024
        self._tokenizer = None
        self._model = None
        self._lock = threading.RLock()
        self._cache: dict[str, list[float]] = {}

    def _load(self) -> None:
        if self._model is not None:
            return
        if not self.path.is_dir():
            raise RagModelError(f"Local BGE-M3 model is missing: {self.path}")
        try:
            from transformers import AutoModel, AutoTokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(str(self.path), local_files_only=True)
            self._model = AutoModel.from_pretrained(str(self.path), local_files_only=True).eval()
        except Exception as exc:
            raise RagModelError(f"Unable to load local BGE-M3: {exc}") from exc

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        with self._lock:
            missing = list(dict.fromkeys(text for text in texts if hashlib.sha256(text.encode("utf-8")).hexdigest() not in self._cache))
            if missing:
                self._load()
                import torch
                import torch.nn.functional as functional
                for start in range(0, len(missing), 8):
                    batch = missing[start:start + 8]
                    tokens = self._tokenizer(batch, padding=True, truncation=True,
                                             max_length=512, return_tensors="pt")
                    with torch.inference_mode():
                        outputs = self._model(**tokens)
                        vectors = functional.normalize(outputs.last_hidden_state[:, 0].float(), p=2, dim=1)
                    for text, vector in zip(batch, vectors.tolist()):
                        if len(vector) != self.dimension:
                            raise RagModelError("BGE-M3 embedding dimension changed")
                        self._cache[hashlib.sha256(text.encode("utf-8")).hexdigest()] = vector
            return [self._cache[hashlib.sha256(text.encode("utf-8")).hexdigest()] for text in texts]


