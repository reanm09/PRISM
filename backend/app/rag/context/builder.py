import logging
from typing import List, Optional, Tuple

from app.rag.schemas.rag import SourceCitation
from app.rag.schemas.retrieval import RetrievalResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the PRISM RAG Assistant, an evidence-grounded truth engine component.
Your purpose is to answer questions strictly using the retrieved knowledge supplied below.

CRITICAL INSTRUCTIONS:
1. Answer using ONLY the retrieved knowledge provided. Do NOT invent, assume, or hallucinate facts that are not explicitly present in the retrieved context.
2. If the retrieved context is empty or does not contain sufficient information to answer the question, you MUST explicitly state:
"The available PRISM knowledge base does not contain enough information to answer this question."
3. Distinguish retrieved evidence from any inference.
4. When possible, cite the source title (e.g. "[Dennis Ritchie]") supporting your statement.
5. Adhere to the core PRISM principle: "The LLM proposes. The experiment decides." Never claim that retrieval alone constitutes empirical proof."""


class ContextBuilder:
    """
    Constructs structured context and citations from retrieval results.
    """

    def __init__(self, system_prompt: str = SYSTEM_PROMPT):
        self.system_prompt = system_prompt

    def build_context(self, results: List[RetrievalResult]) -> Tuple[str, List[SourceCitation]]:
        if not results:
            return "No relevant knowledge documents found in the PRISM database.", []

        context_blocks: List[str] = []
        citations: List[SourceCitation] = []

        for idx, item in enumerate(results, start=1):
            source_block = (
                f"[Source {idx}: {item.title}]\n"
                f"Category: {item.category}\n"
                f"Relevance: {item.similarity:.2f}\n"
                f"Content:\n{item.content.strip()}"
            )
            context_blocks.append(source_block)

            citations.append(
                SourceCitation(
                    chunk_id=item.chunk_id,
                    title=item.title,
                    category=item.category,
                    similarity=item.similarity,
                    snippet=item.content[:150] + ("..." if len(item.content) > 150 else ""),
                )
            )

        full_context = "\n\n" + ("=" * 40) + "\n\n".join([""] + context_blocks) + "\n\n" + ("=" * 40)
        return full_context, citations

    def format_prompt(self, question: str, context: str) -> str:
        prompt = (
            f"CURRENT QUESTION:\n{question}\n\n"
            f"RETRIEVED KNOWLEDGE CONTEXT:\n{context}\n\n"
            f"Provide a clear, concise, grounded answer (1-3 sentences) citing the supporting source title when applicable. "
            f"If the knowledge base cannot answer the question, state so directly."
        )
        return prompt
