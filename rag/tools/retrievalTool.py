"""Smolagents Tool wrapper for the user's personal writing retriever."""

from typing import List
from smolagents import Tool
from .vector_store import ChromaRetriever


class RetrieveWritingsTool(Tool):
    """
    Semantic search over a user's uploaded writing samples.
    Adapted directly from your RAG assignment's RetrieveDocumentsTool.
    """

    name = "retrieveWritings"
    description = (
        "Search the user's uploaded writing samples using semantic similarity. "
        "Use this to find examples of how they write — their vocabulary, sentence "
        "structure, dialogue style, pacing, and narrative voice."
    )
    inputs = {
        "query": {
            "type": "string",
            "description": "What aspect of their writing to look for, e.g. 'action scene descriptions' or 'how they write dialogue'.",
        },
        "topK": {
            "type": "integer",
            "description": "Number of writing samples to retrieve.",
            "default": 6,
            "nullable": True,
        },
    }
    outputType = "array"

    def __init__(self, retriever: ChromaRetriever) -> None:
        super().__init__()
        self.retriever = retriever

    def forward(self, query: str, topK: int = 6) -> List[dict]:
        return self.retriever.retrieve(query=query, limit=topK)