"""
Continuation Agent
Seamlessly continues the story from the last paragraph the writer provided,
matching their voice, style, and story context exactly.
"""

from __future__ import annotations

import requests
from ..tools.vectorStore import ChromaRetriever

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"
RAG_TOP_K = 5


def continueWriting(
    lastParagraph: str,
    retriever: ChromaRetriever,
    styleProfile: dict,
    storyPatterns: dict,
    characterProfiles: dict,
) -> dict:
    """
    Continue the story from where the writer left off.

    Args:
        lastParagraph:     The last paragraph(s) the writer wrote.
        retriever:         User's ChromaRetriever for style and story grounding.
        styleProfile:      Combined style profile (keys: sentences, vocabulary, tone).
        storyPatterns:     Narrative pattern profile.
        characterProfiles: Characters present in the story.

    Returns:
        dict with keys: continuation, sourcesUsed
    """
    relevantChunks = retriever.retrieve(query=lastParagraph, limit=RAG_TOP_K)
    writingContext  = "\n\n---\n\n".join(r["document"] for r in relevantChunks)
    sources         = list({r["metadata"].get("source", "unknown") for r in relevantChunks})

    sentenceSection  = styleProfile.get("sentences", {})
    vocabularySection = styleProfile.get("vocabulary", {})
    toneSection       = styleProfile.get("tone", {})

    rhythm      = sentenceSection.get("rhythm", "") if isinstance(sentenceSection, dict) else ""
    register    = vocabularySection.get("register", "") if isinstance(vocabularySection, dict) else ""
    petWords    = vocabularySection.get("petWords", "") if isinstance(vocabularySection, dict) else ""
    primaryTone = toneSection.get("primaryTone", "") if isinstance(toneSection, dict) else ""
    pacing      = storyPatterns.get("pacing", "")
    narrativePOV = storyPatterns.get("narrativePOV", "")

    characters = ", ".join(
        c.get("name", "") for c in characterProfiles.get("characters", [])
    )

    systemPrompt = (
        "You are a writing assistant. Your ONLY job is to continue the story in the author's "
        "exact voice — same rhythm, register, tone, and point of view. Do NOT impose your own style.\n\n"
        "=== AUTHOR'S STYLE ===\n"
        f"Sentence rhythm: {rhythm}\n"
        f"Vocabulary register: {register}\n"
        f"Recurring words/phrases: {petWords}\n"
        f"Tone: {primaryTone}\n"
        f"Pacing: {pacing}\n"
        f"POV: {narrativePOV}\n\n"
        f"Active characters: {characters}\n\n"
        "=== AUTHOR'S WRITING (mirror this style exactly) ===\n"
        f"{writingContext}"
    )

    userMessage = (
        "Continue the story from exactly where this ends. "
        "Write 1-3 paragraphs. Do not summarize or explain — just write the next part.\n\n"
        f"LAST PARAGRAPH:\n{lastParagraph}"
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": userMessage, "system": systemPrompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        return {
            "continuation": response.json().get("response", "").strip(),
            "sourcesUsed":  sources,
        }
    except requests.RequestException as e:
        return {"error": f"Ollama request failed: {e}", "continuation": None, "sourcesUsed": []}
