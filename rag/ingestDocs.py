#!/usr/bin/env python3
"""
Ingests uploaded writing samples into a per-user ChromaDB collection.
Supports: .pdf, .txt, .md, .docx
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import chromadb
import pdfplumber
import docx as python_docx
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ── Chunking config ────────────────────────────────────────────────────────────
CHUNK_SIZE    = 400   # Smaller than your ML assignment — better for style capture
CHUNK_OVERLAP = 80

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}


# ── Text extraction ────────────────────────────────────────────────────────────

def extractPdf(path: Path) -> str:
    pages = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text)
    return "\n\n".join(pages)


def extractTxt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def extractDocx(path: Path) -> str:
    doc = python_docx.Document(str(path))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extractText(path: Path) -> str:
    """Dispatch to the right extractor based on file extension."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return extractPdf(path)
    elif ext in {".txt", ".md"}:
        return extractTxt(path)
    elif ext == ".docx":
        return extractDocx(path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


# ── Chunking ───────────────────────────────────────────────────────────────────

def chunkText(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " "],
    )
    return splitter.split_text(text)


# ── Ingestion ──────────────────────────────────────────────────────────────────

def ingestFile(
    path: Path,
) -> tuple[list[str], list[dict], list[str]]:
    """Extract, chunk, and build ChromaDB records for a single file."""
    text = extractText(path)
    chunks = chunkText(text)

    documents: list[str] = []
    metadatas: list[dict] = []
    ids:       list[str] = []

    for i, chunk in enumerate(chunks):
        documents.append(chunk)
        metadatas.append({
            "source":     path.name,
            "fileType":  path.suffix.lower(),
            "chunkIndex": i,
        })
        ids.append(f"{path.stem}-c{i}")

    return documents, metadatas, ids


def ingestForUser(
    filePath: Path,
    userId: str,
    vectorStoreDir: Path,
) -> dict:
    """
    Ingest a single uploaded file into the user's personal ChromaDB collection.
    Called directly from your Flask /upload route after saving the file.

    Returns a summary dict.
    """
    if filePath.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{filePath.suffix}'. "
            f"Allowed: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    documents, metadatas, ids = ingestFile(filePath)

    if not documents:
        raise ValueError(f"No extractable text found in {filePath.name}")

    # Each user gets their own isolated collection
    collectionName = f"user_{userId}_writings"

    client = chromadb.PersistentClient(path=str(vectorStoreDir))
    embeddingFn = SentenceTransformerEmbeddingFunction(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    collection = client.get_or_create_collection(
        name=collectionName,
        embedding_function=embeddingFn,
    )

    # Remove any previous chunks from this exact file so re-uploads don't duplicate
    existing = collection.get(where={"source": filePath.name})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])

    collection.add(ids=ids, documents=documents, metadatas=metadatas)

    return {
        "collection": collectionName,
        "file":       filePath.name,
        "chunks":     len(documents),
        "totalDocsInCollection": collection.count(),
    }