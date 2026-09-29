from abc import ABC, abstractmethod
from typing import List

from app.rag.schemas.document import Document, DocumentChunk


class Chunker(ABC):
    @abstractmethod
    def chunk(self, document: Document) -> List[DocumentChunk]:
        """Split a document into one or more structured DocumentChunks."""
        pass
