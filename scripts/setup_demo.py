#!/usr/bin/env python3
"""
Demo Setup Script
Ingests Project Gutenberg sample texts for each demo author into
the isolated demo vector store.

Usage (from project root):
    python scripts/setup_demo.py

Files are organized by author under rag/data/demo/<dir>/ as defined
in rag/demo/authors.py (each author entry has a "dir" and "files" key).

Pass --force to re-ingest authors that are already loaded.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the project root importable regardless of where the script is called from
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag.tools.ingestDocs import ingestForUser
from rag.tools.vectorStore import ChromaRetriever
from rag.demo.authors import DEMO_AUTHORS

DEMO_DATA_DIR         = PROJECT_ROOT / "rag" / "data" / "demo"
DEMO_VECTOR_STORE_DIR = PROJECT_ROOT / "rag" / "data" / "demo" / "vectorStore"


def ingestAuthor(key: str, author: dict, force: bool = False) -> None:
    userId   = f"demo_{key}"
    retriever = ChromaRetriever(persistDirectory=DEMO_VECTOR_STORE_DIR, userId=userId)

    if retriever.count() > 0 and not force:
        print(f"  ✓ {author['name']} already ingested ({retriever.count()} chunks) — skipping. Use --force to re-ingest.")
        return

    authorDir = DEMO_DATA_DIR / author["dir"]
    missingFiles = [f for f in author["files"] if not (authorDir / f).exists()]
    if missingFiles:
        print(f"  ✗ {author['name']}: missing file(s): {', '.join(missingFiles)}")
        print(f"    Download from Project Gutenberg and place in: {authorDir}")
        return

    print(f"  → Ingesting {author['name']} ({len(author['files'])} file(s))...")
    totalChunks = 0

    for filename in author["files"]:
        filePath = authorDir / filename
        try:
            summary = ingestForUser(
                filePath=filePath,
                userId=userId,
                vectorStoreDir=DEMO_VECTOR_STORE_DIR,
            )
            chunks = summary.get("chunksIngested", 0)
            totalChunks += chunks
            print(f"    {filename}: {chunks} chunks")
        except Exception as e:
            print(f"    ✗ {filename}: {e}")

    print(f"  ✓ {author['name']}: {totalChunks} total chunks ingested")


def main() -> None:
    parser = argparse.ArgumentParser(description="Set up demo author data")
    parser.add_argument("--force", action="store_true", help="Re-ingest authors that already have data")
    parser.add_argument("--author", metavar="KEY", help="Ingest only this author (e.g. poe, austen)")
    args = parser.parse_args()

    DEMO_VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)

    authors = (
        {args.author: DEMO_AUTHORS[args.author]}
        if args.author and args.author in DEMO_AUTHORS
        else DEMO_AUTHORS
    )

    if args.author and args.author not in DEMO_AUTHORS:
        print(f"Unknown author key: {args.author}")
        print(f"Available keys: {', '.join(DEMO_AUTHORS)}")
        sys.exit(1)

    print(f"\nDemo Setup — ingesting {len(authors)} author(s) into {DEMO_VECTOR_STORE_DIR}\n")
    for key, author in authors.items():
        ingestAuthor(key, author, force=args.force)

    print("\nDone. Start the app and open Demo Mode to test.\n")


if __name__ == "__main__":
    main()
