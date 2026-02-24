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


def buildStyleProfile(retriever: ChromaRetriever) -> dict:
    """
    Convenience wrapper — returns the full style profile dict.
    Called directly from the /styleProfile Flask route.
    """
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

    # 1. Analyze the user's writing style
    styleProfile = analyzeStyle(retriever)

    # 2. Detect their narrative/story patterns
    storyPatterns = detectStoryPatterns(retriever)

    # 3. Generate text using both profiles as context
    generation = generateInVoice(
        prompt=prompt,
        retriever=retriever,
        styleProfile=styleProfile,
        storyPatterns=storyPatterns,
        styleHint=styleHint,
    )

    return {
        "generatedText": generation.get("generatedText"),
        "styleProfile":  styleProfile,
        "storyPatterns": storyPatterns,
        "sourcesUsed":   generation.get("sourcesUsed", []),
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