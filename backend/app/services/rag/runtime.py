"""Process-wide PRISM RAG runtime.

All production consumers share this instance so the persisted index,
in-memory chunk cache, embedder, and generator have one lifecycle.
"""

from app.services.rag.service import RagService


rag_service = RagService()
