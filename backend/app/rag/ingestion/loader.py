import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from app.rag.config.rag_config import rag_settings

from app.rag.schemas.document import Document

logger = logging.getLogger(__name__)


class DocumentLoader(ABC):
    @abstractmethod
    def load(self) -> List[Document]:
        """Loads and returns a list of Document objects."""
        pass

class DirectoryDocumentLoader(DocumentLoader):
    """
    Loads text/markdown documents from the real PRISM knowledge directory
    (e.g., specs, parser-docs, research, advisories, artifact-passports, semantic-fractures, experiments).
    """

    def __init__(self, directory_path: Optional[Path] = None):
        self.directory_path = Path(directory_path or rag_settings.knowledge_root)

    def load(self) -> List[Document]:
        if not self.directory_path.exists():
            logger.warning("Knowledge directory %s does not exist", self.directory_path)
            return []

        documents: List[Document] = []
        for file_path in sorted(self.directory_path.glob("**/*")):
            if file_path.is_file() and file_path.suffix.lower() in [".md", ".txt", ".json"]:
                try:
                    content = file_path.read_text(encoding="utf-8")
                    rel_parts = file_path.relative_to(self.directory_path).parts
                    category = " / ".join(rel_parts[:-1]) if len(rel_parts) > 1 else "general"

                    # Extract title from markdown H1 if present
                    title = file_path.stem.replace("_", " ").title()
                    h1_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                    if h1_match:
                        title = h1_match.group(1).strip()

                    doc = Document(
                        title=title,
                        category=category,
                        content=content,
                        metadata={
                            "document_type": "knowledge",
                            "source": str(file_path),
                            "filename": file_path.name,
                            "topic": rel_parts[0] if rel_parts else "general",
                        },
                    )
                    documents.append(doc)
                except Exception as exc:
                    logger.error("Failed to read %s: %s", file_path, exc)

        logger.info("Loaded %d real PRISM documents from %s", len(documents), self.directory_path)
        return documents


class CompositeDocumentLoader(DocumentLoader):
    """
    Combines mock seed documents and real PRISM directory knowledge documents.
    """

    def __init__(
        self,
        include_mock: bool = True,
        include_real: bool = True,
        directory_path: Optional[Path] = None,
    ):
        self.include_mock = include_mock
        self.include_real = include_real
        self.directory_path = directory_path

    def load(self) -> List[Document]:
        docs: List[Document] = []

        if self.include_real:
            docs.extend(DirectoryDocumentLoader(self.directory_path).load())
        logger.info("CompositeDocumentLoader loaded total %d documents", len(docs))
        return docs
