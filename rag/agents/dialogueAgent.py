"""
Dialogue Agent
Writes dialogue between specific characters in the author's voice,
grounded in each character's established personality and speech patterns.
"""

from __future__ import annotations

import requests
from ..tools.vectorStore import ChromaRetriever

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"
RAG_TOP_K    = 5


def writeDialogue(
    context: str,
    retriever: ChromaRetriever,
    styleProfile: dict,
    characterProfiles: dict,
    characters: list[str] | None = None,
) -> dict:
    """
    Write dialogue between specified characters in the author's voice.

    Args:
        context:           What is happening around this dialogue / what it's about.
        retriever:         User's ChromaRetriever.
        styleProfile:      Combined style profile (keys: sentences, vocabulary, tone).
        characterProfiles: Known characters with descriptions.
        characters:        Names of characters who are speaking.

    Returns:
        dict with keys: dialogue, sourcesUsed
    """
    charNames = characters or []
    dialogueQuery = " ".join(filter(None, ["dialogue conversation speaking"] + charNames)).strip()
    relevantChunks = retriever.retrieve(query=dialogueQuery, limit=RAG_TOP_K)
    writingContext  = "\n\n---\n\n".join(r["document"] for r in relevantChunks)
    sources         = list({r["metadata"].get("source", "unknown") for r in relevantChunks})

    # Build per-character context
    charContext = ""
    if charNames and characterProfiles.get("characters"):
        matched = [
            c for c in characterProfiles["characters"]
            if c.get("name", "") in charNames
        ]
        if matched:
            charContext = "\n".join(
                f"- {c['name']}: {c.get('description', '')} | "
                f"Motivation: {c.get('motivation', '')} | "
                f"Relationships: {c.get('relationships', '')}"
                for c in matched
            )

    sentenceSection   = styleProfile.get("sentences", {})
    vocabularySection = styleProfile.get("vocabulary", {})
    toneSection       = styleProfile.get("tone", {})

    rhythm      = sentenceSection.get("rhythm", "") if isinstance(sentenceSection, dict) else ""
    register    = vocabularySection.get("register", "") if isinstance(vocabularySection, dict) else ""
    petWords    = vocabularySection.get("petWords", "") if isinstance(vocabularySection, dict) else ""
    primaryTone = toneSection.get("primaryTone", "") if isinstance(toneSection, dict) else ""

    systemPrompt = (
        "You are a writing assistant. Write dialogue that sounds like it belongs in this author's work "
        "— matching their dialogue style, character voices, and subtext.\n\n"
        "=== AUTHOR'S DIALOGUE STYLE ===\n"
        f"Sentence rhythm: {rhythm}\n"
        f"Vocabulary register: {register}\n"
        f"Recurring phrases: {petWords}\n"
        f"Tone: {primaryTone}\n\n"
        + (f"=== SPEAKING CHARACTERS ===\n{charContext}\n\n" if charContext else "")
        + "=== AUTHOR'S EXISTING DIALOGUE (match this style) ===\n"
        f"{writingContext}"
    )

    charLine = f"Characters speaking: {', '.join(charNames)}\n" if charNames else ""

    userMessage = (
        "Write dialogue for this situation:\n"
        f"{charLine}"
        f"Context: {context}\n\n"
        "Write the dialogue directly — include action beats only if the author's style uses them. "
        "Each character should sound distinct based on their profile."
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": userMessage, "system": systemPrompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        return {
            "dialogue":    response.json().get("response", "").strip(),
            "sourcesUsed": sources,
        }
    except requests.RequestException as e:
        return {"error": f"Ollama request failed: {e}", "dialogue": None, "sourcesUsed": []}
