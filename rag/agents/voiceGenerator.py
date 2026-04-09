"""
Voice Generator Agent
The final generation step — takes a prompt, style profile, story patterns,
and RAG context, then generates text that mirrors the user's voice as closely
as possible.
"""

from __future__ import annotations

import requests
import os
from pathlib import Path
from ..tools.vectorStore import ChromaRetriever

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"
RAG_TOP_K    = 6


def generateInVoice(
    prompt: str,
    retriever: ChromaRetriever,
    styleProfile: dict,
    storyPatterns: dict,
    styleHint: str = "",
) -> dict:
    """
    Generate text in the user's voice using all available context.

    Args:
        prompt:        What the user wants written.
        retriever:     Their personal ChromaRetriever for RAG chunks.
        styleProfile:  Output from styleAnalyzer.analyzeStyle()
        storyPatterns: Output from storyDetector.detectStoryPatterns()
        styleHint:     Optional freeform instruction from the user.

    Returns:
        dict with keys: generatedText, sourcesUsed
    """
    # 1. Retrieve the most relevant writing chunks for this specific prompt
    relevantChunks = retriever.retrieve(query=prompt, limit=RAG_TOP_K)
    writingContext  = "\n\n---\n\n".join(r["document"] for r in relevantChunks)
    sources         = list({r["metadata"].get("source", "unknown") for r in relevantChunks})

    if not writingContext:
        return {
            "error": "No relevant writing samples found to generate from.",
            "generatedText": None,
            "sourcesUsed": [],
        }

    # 2. Build the system prompt from the style and story analysis.
    # styleProfile is a nested dict with keys: sentences, vocabulary, tone.
    sentenceSection   = styleProfile.get("sentences", {})
    vocabularySection = styleProfile.get("vocabulary", {})
    toneSection       = styleProfile.get("tone", {})

    sentenceStyle = (
        sentenceSection.get("rhythm", sentenceSection.get("raw", ""))
        if isinstance(sentenceSection, dict) else str(sentenceSection)
    )
    vocabulary = (
        vocabularySection.get("register", vocabularySection.get("raw", ""))
        if isinstance(vocabularySection, dict) else str(vocabularySection)
    )
    tone = (
        toneSection.get("primaryTone", toneSection.get("raw", ""))
        if isinstance(toneSection, dict) else str(toneSection)
    )
    habits = (
        sentenceSection.get("patterns", "")
        if isinstance(sentenceSection, dict) else ""
    )
    styleSummary = f"Sentences: {sentenceStyle} | Vocabulary: {vocabulary} | Tone: {tone}"

    arcType       = storyPatterns.get("arcType", "")
    pacing        = storyPatterns.get("pacing", "")
    narrativePOV  = storyPatterns.get("narrativePOV", "")

    systemPrompt = (
        "You are a writing assistant. Your ONLY job is to generate text that is "
        "indistinguishable from the author's own writing. Do not default to a generic style.\n\n"
        "=== AUTHOR STYLE PROFILE ===\n"
        f"Overall: {styleSummary}\n"
        f"Sentences: {sentenceStyle}\n"
        f"Vocabulary: {vocabulary}\n"
        f"Tone: {tone}\n"
        f"Distinctive habits: {habits}\n\n"
        "=== NARRATIVE PATTERNS ===\n"
        f"Story arc preference: {arcType}\n"
        f"Pacing: {pacing}\n"
        f"Point of view: {narrativePOV}\n\n"
        "=== WRITING SAMPLES (mirror these exactly) ===\n"
        f"{writingContext}"
    )

    userMessage = f"Task: {prompt}"
    if styleHint:
        userMessage += f"\nAdditional guidance from the author: {styleHint}"

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": userMessage, "system": systemPrompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        return {
            "generatedText": response.json().get("response", "").strip(),
            "sourcesUsed":   sources,
        }
    except requests.RequestException as e:
        return {"error": f"Ollama request failed: {e}", "generatedText": None, "sourcesUsed": []}