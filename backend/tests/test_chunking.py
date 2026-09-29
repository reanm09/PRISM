import unittest
from app.rag.chunking.chunker import StandardDocumentChunker
from app.rag.schemas.document import Document


class TestChunking(unittest.TestCase):
    def setUp(self):
        self.chunker = StandardDocumentChunker(max_chunk_size=100)

    def test_single_chunk_small_doc(self):
        doc = Document(
            title="Dennis Ritchie",
            category="person / computer_science",
            content="Dennis Ritchie created the C programming language.",
            metadata={"source": "test"}
        )
        chunks = self.chunker.chunk(doc)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].title, "Dennis Ritchie")
        self.assertEqual(chunks[0].metadata.chunk_index, 0)
        self.assertIsNotNone(chunks[0].metadata.chunk_hash)

    def test_multi_chunk_large_doc(self):
        large_content = (
            "Paragraph one is about initial systems and language design.\n\n"
            "Paragraph two delves into operating system kernel implementations.\n\n"
            "Paragraph three covers compiler pipelines and optimization passes."
        )
        doc = Document(
            title="Systems Architecture",
            category="systems / engineering",
            content=large_content,
            metadata={"source": "test"}
        )
        chunks = self.chunker.chunk(doc)
        self.assertGreater(len(chunks), 1)
        # Verify deterministic hash
        hash_1 = chunks[0].metadata.chunk_hash
        chunks_repeat = self.chunker.chunk(doc)
        self.assertEqual(hash_1, chunks_repeat[0].metadata.chunk_hash)


if __name__ == "__main__":
    unittest.main()
