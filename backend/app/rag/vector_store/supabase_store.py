import json
import logging
import math
from typing import Any, Dict, List, Optional

from app.database import supabase
from app.rag.schemas.document import DocumentChunk
from app.rag.schemas.retrieval import RetrievalResult
from app.rag.vector_store.base import VectorStore

logger = logging.getLogger(__name__)


def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 < 1e-9 or norm2 < 1e-9:
        return 0.0
    return dot / (norm1 * norm2)


class SupabaseVectorStore(VectorStore):
    """
    Vector store implementation backed by Supabase PostgreSQL and pgvector.
    Leverages the `rag_knowledge` table and `match_rag_knowledge` RPC function.
    """

    def __init__(self, table_name: str = "rag_knowledge", client=None):
        self.table_name = table_name
        self.client = client or supabase

    def add_documents(
        self,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]],
    ) -> List[str]:
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks and embeddings must match")

        inserted_ids: List[str] = []

        for chunk, emb in zip(chunks, embeddings):
            chunk_hash = chunk.metadata.chunk_hash or ""
            
            # Check for existing document to avoid duplicate insertions
            existing = None
            try:
                res = self.client.table(self.table_name).select("id, title, metadata").eq("title", chunk.title).execute()
                if res.data:
                    for row in res.data:
                        row_meta = row.get("metadata") or {}
                        if row_meta.get("chunk_hash") == chunk_hash:
                            existing = row
                            break
            except Exception as exc:
                logger.warning("Error checking for existing chunk %s: %s", chunk.title, exc)

            record_payload = {
                "title": chunk.title,
                "category": chunk.category,
                "content": chunk.content,
                "metadata": chunk.metadata.model_dump(),
                "embedding": emb,
            }

            if existing:
                row_id = existing["id"]
                logger.info("Chunk already exists for '%s' (id: %s). Updating vector.", chunk.title, row_id)
                self.client.table(self.table_name).update(record_payload).eq("id", row_id).execute()
                inserted_ids.append(row_id)
            else:
                logger.info("Inserting new knowledge chunk '%s' into %s.", chunk.title, self.table_name)
                # Let Supabase generate UUID if chunk_id is not already standard
                insert_data = record_payload.copy()
                if chunk.chunk_id:
                    try:
                        # Test if chunk.chunk_id is valid UUID
                        import uuid
                        uuid.UUID(chunk.chunk_id)
                        insert_data["id"] = chunk.chunk_id
                    except ValueError:
                        pass
                
                resp = self.client.table(self.table_name).insert(insert_data).execute()
                if resp.data:
                    inserted_ids.append(resp.data[0]["id"])

        return inserted_ids

    def similarity_search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        match_threshold: float = 0.0,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievalResult]:
        # 1. Primary path: Use Supabase pgvector RPC `match_rag_knowledge`
        try:
            rpc_res = self.client.rpc("match_rag_knowledge", {
                "query_embedding": query_embedding,
                "match_threshold": match_threshold,
                "match_count": top_k,
            }).execute()

            if rpc_res.data is not None:
                results: List[RetrievalResult] = []
                for row in rpc_res.data:
                    category = row.get("category") or ""
                    # Apply optional filters
                    if filters:
                        if "category" in filters and filters["category"]:
                            if filters["category"].lower() not in category.lower():
                                continue

                    results.append(
                        RetrievalResult(
                            chunk_id=str(row.get("id")),
                            title=row.get("title", ""),
                            content=row.get("content", ""),
                            category=category,
                            metadata=row.get("metadata") or {},
                            similarity=float(row.get("similarity", 0.0)),
                        )
                    )
                return results

        except Exception as exc:
            logger.warning("match_rag_knowledge RPC query failed: %s. Falling back to table scan.", exc)

        # 2. Fallback path: Direct query with in-memory similarity computation
        try:
            q = self.client.table(self.table_name).select("*")
            if filters and "category" in filters and filters["category"]:
                q = q.ilike("category", f"%{filters['category']}%")
            table_res = q.execute()

            scored: List[RetrievalResult] = []
            if table_res.data:
                for row in table_res.data:
                    emb_raw = row.get("embedding")
                    if isinstance(emb_raw, str):
                        emb = json.loads(emb_raw)
                    elif isinstance(emb_raw, list):
                        emb = emb_raw
                    else:
                        continue

                    sim = _cosine_similarity(query_embedding, emb)
                    if sim >= match_threshold:
                        scored.append(
                            RetrievalResult(
                                chunk_id=str(row.get("id")),
                                title=row.get("title", ""),
                                content=row.get("content", ""),
                                category=row.get("category", ""),
                                metadata=row.get("metadata") or {},
                                similarity=round(sim, 4),
                            )
                        )

            scored.sort(key=lambda r: r.similarity, reverse=True)
            return scored[:top_k]

        except Exception as exc:
            logger.error("Direct table similarity search failed: %s", exc)
            return []

    def delete(self, chunk_ids: List[str]) -> bool:
        try:
            for cid in chunk_ids:
                self.client.table(self.table_name).delete().eq("id", cid).execute()
            return True
        except Exception as exc:
            logger.error("Error deleting chunks: %s", exc)
            return False

    def get(self, chunk_id: str) -> Optional[RetrievalResult]:
        try:
            res = self.client.table(self.table_name).select("*").eq("id", chunk_id).execute()
            if res.data:
                row = res.data[0]
                return RetrievalResult(
                    chunk_id=str(row.get("id")),
                    title=row.get("title", ""),
                    content=row.get("content", ""),
                    category=row.get("category", ""),
                    metadata=row.get("metadata") or {},
                    similarity=1.0,
                )
            return None
        except Exception as exc:
            logger.error("Error getting chunk %s: %s", chunk_id, exc)
            return None
