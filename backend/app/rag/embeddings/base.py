from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def dimension(self) -> int:
        """Returns the embedding vector dimension."""
        pass

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embeds a list of texts into dense vectors."""
        pass

    def embed_text(self, text: str) -> List[float]:
        """Convenience method to embed a single string."""
        return self.embed([text])[0]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Convenience method to embed multiple document chunks."""
        return self.embed(texts)
