"""
Writing agent — generates text in the user's voice using RAG over their uploads.
Uses Ollama locally (no API key, no data leaves the machine).
"""

from __future__ import annotations

import requests
from pathlib import Path
from ..tools.vectorStore import ChromaRetriever
from .styleAnalyzer import analyzeStyle
from .storyDetector import detectStoryPatterns
from .ideaGenerator import generateIdeas
from .voiceGenerator import generateInVoice
from .profileCache import loadCache, saveCache
from .paragraphAnalyzer import analyzeParagraphs

# Cache lives alongside the other data directories
_CACHE_DIR_NAME = "cache"


def _cacheDir(vectorStoreDir: Path) -> Path:
    return vectorStoreDir.parent / _CACHE_DIR_NAME


def _getProfiles(retriever: ChromaRetriever, userId: str, vectorStoreDir: Path) -> tuple[dict, dict, dict]:
    """
    Return (styleProfile, storyPatterns, paragraphStats), pulling from cache when valid.
    Runs all three analyses and writes a fresh cache when the cache is stale or missing.
    """
    docCount = retriever.count()
    cached = loadCache(_cacheDir(vectorStoreDir), userId, docCount)
    if cached:
        return cached["styleProfile"], cached["storyPatterns"], cached["paragraphStats"]

    styleProfile   = analyzeStyle(retriever)
    storyPatterns  = detectStoryPatterns(retriever)
    paragraphStats = analyzeParagraphs(retriever)
    saveCache(_cacheDir(vectorStoreDir), userId, styleProfile, storyPatterns, paragraphStats, docCount)
    return styleProfile, storyPatterns, paragraphStats


def buildStyleProfile(retriever: ChromaRetriever, userId: str = "default", vectorStoreDir: Path | None = None) -> dict:
    """
    Convenience wrapper — returns the full style profile dict.
    Called directly from the /styleProfile Flask route.
    Uses cache when available.
    """
    if vectorStoreDir is not None:
        styleProfile, _, _ = _getProfiles(retriever, userId, vectorStoreDir)
        return styleProfile
    return analyzeStyle(retriever)


def generateInUserVoice(
    prompt: str,
    userId: str,
    vectorStoreDir: Path,
    styleHint: str = "",
) -> dict:
    """
    Main entry point called from Flask /generate.
    Runs all four sub-agents in sequence and returns the final generated text.

    Args:
        prompt:         What the user wants written.
        userId:         Used to look up their personal ChromaDB collection.
        vectorStoreDir: Path to ChromaDB storage.
        styleHint:      Optional freeform style instruction from the user.

    Returns:
        dict with keys: generatedText, styleProfile, storyPatterns, sourcesUsed
    """
    retriever = ChromaRetriever(
        persistDirectory=vectorStoreDir,
        userId=userId,
    )

    if retriever.count() == 0:
        return {
            "error": "No writing samples uploaded yet. Please upload some of your work first.",
            "generatedText": None,
            "styleProfile":  None,
            "storyPatterns": None,
            "sourcesUsed":   [],
        }

    # 1, 2 & 3. Get profiles (from cache if available)
    styleProfile, storyPatterns, paragraphStats = _getProfiles(retriever, userId, vectorStoreDir)

    # 3. Generate text using both profiles as context
    generation = generateInVoice(
        prompt=prompt,
        retriever=retriever,
        styleProfile=styleProfile,
        storyPatterns=storyPatterns,
        styleHint=styleHint,
    )

    return {
        "generatedText":  generation.get("generatedText"),
        "styleProfile":   styleProfile,
        "storyPatterns":  storyPatterns,
        "paragraphStats": paragraphStats,
        "sourcesUsed":    generation.get("sourcesUsed", []),
    }


def getWritingIdeas(
    userId: str,
    vectorStoreDir: Path,
    topic: str = "",
    count: int = 5,
) -> dict:
    """
    Entry point for the /ideas Flask route.
    Returns story ideas tailored to the user's style.
    """
    retriever = ChromaRetriever(
        persistDirectory=vectorStoreDir,
        userId=userId,
    )

    if retriever.count() == 0:
        return {"error": "No writing samples uploaded yet. Please upload some of your work first."}

    return generateIdeas(retriever=retriever, topic=topic, count=count)