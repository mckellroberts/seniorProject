"""ChromaDB-backed retrieval — adapted from your RAG assignment."""

from pathlib import Path
from typing import List, Optional

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction


class ChromaRetriever:
    """
    Thin wrapper around a per-user ChromaDB collection.
    Identical interface to your assignment's ChromaRetriever.
    """

    def __init__(
        self,
        persistDirectory: Path,
        userId: str,
        embeddingModel: str = "sentence-transformers/all-MiniLM-L6-v2",
        maxResults: int = 6,
    ) -> None:
        self.persistDirectory = Path(persistDirectory)
        self.userId = userId
        self.maxResults = maxResults
        self.collectionName = f"user_{userId}_writings"

        self._client = chromadb.PersistentClient(path=str(self.persistDirectory))
        self._embeddingFn = SentenceTransformerEmbeddingFunction(model_name=embeddingModel)
        self._collection = self._client.get_or_create_collection(
            name=self.collectionName,
            embedding_function=self._embeddingFn,
        )

    def retrieve(self, query: str, limit: Optional[int] = None) -> List[dict]:
        """Return top-matching chunks with metadata and distance scores."""
        if not query:
            raise ValueError("Query must be a non-empty string.")

        n = limit or self.maxResults

        # Can't query more docs than exist
        available = self._collection.count()
        if available == 0:
            return []
        n = min(n, available)

        response = self._collection.query(query_texts=[query], n_results=n)

        documents = response.get("documents", [[]])[0]
        metadatas = response.get("metadatas", [[]])[0]
        distances = response.get("distances", [[]])[0]

        return [
            {
                "document": doc,
                "metadata": metadatas[i] if i < len(metadatas) else {},
                "distance": distances[i] if i < len(distances) else None,
            }
            for i, doc in enumerate(documents)
        ]

    def listSources(self) -> List[str]:
        """Return unique filenames that have been ingested for this user."""
        results = self._collection.get(include=["metadatas"])
        sources = {m.get("source", "unknown") for m in results["metadatas"]}
        return sorted(sources)

    def deleteSource(self, filename: str) -> int:
        """Remove all chunks belonging to a specific uploaded file."""
        existing = self._collection.get(where={"source": filename})
        if existing["ids"]:
            self._collection.delete(ids=existing["ids"])
        return len(existing["ids"])

    def count(self) -> int:
        return self._collection.count()