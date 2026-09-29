from typing import List
from app.rag.schemas.document import Document

MOCK_DOCUMENTS: List[Document] = [
    Document(
        title="Dennis Ritchie",
        category="person / computer_science",
        content="Dennis Ritchie created the C programming language and co-created the Unix operating system.",
        metadata={
            "document_type": "knowledge",
            "topic": "computer_science",
            "source": "mock_seed",
            "author": "PRISM Seed",
        },
    ),
    Document(
        title="John Carmack",
        category="person / computer_science",
        content="John Carmack is a renowned programming engineer who worked on foundational 3D game engines associated with Doom and Quake.",
        metadata={
            "document_type": "knowledge",
            "topic": "computer_science",
            "source": "mock_seed",
            "author": "PRISM Seed",
        },
    ),
    Document(
        title="Bjarne Stroustrup",
        category="person / computer_science",
        content="Bjarne Stroustrup designed and implemented C++.",
        metadata={
            "document_type": "knowledge",
            "topic": "computer_science",
            "source": "mock_seed",
            "author": "PRISM Seed",
        },
    ),
]
