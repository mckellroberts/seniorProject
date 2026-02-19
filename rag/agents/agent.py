"""
Writing agent — generates text in the user's voice using RAG over their uploads.
Uses Ollama locally (no API key, no data leaves the machine).
"""

from __future__ import annotations

import requests
from pathlib import Path
from ..tools.vectorStore import ChromaRetriever


OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"

# How many writing sample chunks to pull for context
RAG_TOP_K = 6


def buildStyleProfile(retriever: ChromaRetriever) -> str:
    """
    Pull a broad sample of the user's writing across different aspects
    and summarize their style into a compact profile string.
    """
    aspects = [
        "descriptive prose and scene setting",
        "dialogue and character voice",
        "sentence rhythm and pacing",
        "emotional tone and atmosphere",
    ]

    samples = []
    for aspect in aspects:
        results = retriever.retrieve(query=aspect, limit=2)
        for r in results:
            samples.append(r["document"])

    if not samples:
        return "No writing samples available yet."

    combined = "\n\n---\n\n".join(samples[:8])  # cap context size

    profilePrompt = (
        "You are a literary analyst. Read these writing samples from a single author "
        "and describe their style in 3-4 sentences covering: sentence length and rhythm, "
        "vocabulary level, tone, and any distinctive habits. Be specific and concise.\n\n"
        f"SAMPLES:\n{combined}"
    )

    response = requests.post(
        OLLAMA_URL,
        json={"model": OLLAMA_MODEL, "prompt": profilePrompt, "stream": False},
    )
    response.raise_for_status()
    return response.json().get("response", "").strip()


def generateInUserVoice(
    prompt: str,
    userId: str,
    vectorStoreDir: Path,
    styleHint: str = "",
) -> dict:
    """
    Main entry point called from Flask.
    Retrieves relevant writing samples, builds context, generates text in user's voice.

    Args:
        prompt:           What the user wants written.
        user_id:          Used to look up their personal collection.
        vector_store_dir: Path to ChromaDB storage.
        style_hint:       Optional extra style instruction from the user.

    Returns:
        dict with 'generated_text', 'style_profile', and 'sources_used'.
    """
    retriever = ChromaRetriever(
        persistDirectory=vectorStoreDir,
        userId=userId,
    )

    if retriever.count() == 0:
        return {
            "error": "No writing samples uploaded yet. Please upload some of your work first.",
            "generatedText": None,
            "styleProfile": None,
            "sourcesUsed": [],
        }

    # 1. Retrieve relevant writing samples for this specific prompt
    relevantChunks = retriever.retrieve(query=prompt, limit=RAG_TOP_K)
    writingContext = "\n\n---\n\n".join(r["document"] for r in relevantChunks)
    sources = list({r["metadata"].get("source", "unknown") for r in relevantChunks})

    # 2. Build a style profile from their broader body of work
    styleProfile = buildStyleProfile(retriever)

    # 3. Compose the generation prompt
    systemPrompt = (
        "You are a writing assistant that generates text ONLY in the style of the provided author samples. "
        "Study the samples carefully — their voice, rhythm, word choices, and structure — then continue "
        "or create new content that is indistinguishable from their own writing. "
        "Do NOT default to a generic style. Mirror the author exactly.\n\n"
        f"AUTHOR STYLE PROFILE:\n{styleProfile}\n\n"
        f"WRITING SAMPLES FROM THIS AUTHOR:\n{writingContext}"
    )

    userMessage = f"Task: {prompt}"
    if styleHint:
        userMessage += f"\nAdditional guidance: {style_hint}"

    fullPrompt = f"{userMessage}"

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": fullPrompt,
            "system": systemPrompt,
            "stream": False,
        },
    )
    response.raiseForStatus()

    generated = response.json().get("response", "").strip()

    return {
        "generatedText": generated,
        "styleProfile":  styleProfile,
        "sourcesUsed":   sources,
    }