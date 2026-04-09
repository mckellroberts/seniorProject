"""
Stuck Agent
When a writer is stuck, this agent analyzes their story state and offers
concrete, story-grounded next-step suggestions rooted in the writer's own patterns.
"""

from __future__ import annotations

import requests
from ..tools.vectorStore import ChromaRetriever

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"


def getUnstuckSuggestions(
    retriever: ChromaRetriever,
    styleProfile: dict,
    storyPatterns: dict,
    characterProfiles: dict,
    plotSummary: dict,
    context: str = "",
    count: int = 3,
) -> dict:
    """
    Suggest concrete ways forward when a writer is stuck.

    Args:
        retriever:         User's ChromaRetriever for additional context retrieval.
        styleProfile:      Combined style profile (keys: sentences, vocabulary, tone).
        storyPatterns:     Narrative pattern profile from storyDetector.
        characterProfiles: Character profiles from characterProfiler.
        plotSummary:       Plot state from plotTracker.
        context:           Optional description of where/why the writer is stuck.
        count:             Number of suggestions to return.

    Returns:
        dict with keys: suggestions (list of dicts), suggestionCount, raw
    """
    query = context if context else "story conflict tension turning point decision"
    relevantChunks = retriever.retrieve(query=query, limit=4)
    storyContext = "\n\n---\n\n".join(r["document"] for r in relevantChunks)

    currentState  = plotSummary.get("currentState", "")
    openThreads   = plotSummary.get("openThreads", "")
    characters    = ", ".join(
        c.get("name", "") for c in characterProfiles.get("characters", [])
    )
    arcType       = storyPatterns.get("arcType", "")
    conflictStyle = storyPatterns.get("conflictStyle", "")

    toneSection   = styleProfile.get("tone", {})
    primaryTone   = (
        toneSection.get("primaryTone", "")
        if isinstance(toneSection, dict)
        else str(toneSection)
    )

    stuckContext = f"The writer is stuck here: {context}" if context else "The writer is stuck and needs direction."

    systemPrompt = (
        "You are a story consultant helping a writer who is stuck. Your suggestions must be "
        "SPECIFIC and GROUNDED in the writer's actual story — not generic writing advice.\n\n"
        "=== STORY STATE ===\n"
        f"Current narrative state: {currentState}\n"
        f"Open threads: {openThreads}\n"
        f"Characters in play: {characters}\n\n"
        "=== AUTHOR'S PATTERNS ===\n"
        f"Story arc preference: {arcType}\n"
        f"Conflict style: {conflictStyle}\n"
        f"Tone: {primaryTone}\n\n"
        "=== RELEVANT STORY MATERIAL ===\n"
        f"{storyContext}"
    )

    userMessage = (
        f"{stuckContext}\n\n"
        f"Give {count} specific, actionable suggestions for what could happen next. "
        "Each suggestion must reference the existing story, characters, or open threads.\n\n"
        "Format each suggestion as:\n"
        "SUGGESTION: (what could happen next — one paragraph)\n"
        "ROOTED_IN: (which existing story element this builds on)\n"
        "FITS_BECAUSE: (why this matches the author's natural patterns)\n"
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": userMessage, "system": systemPrompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        raw = response.json().get("response", "").strip()
    except requests.RequestException as e:
        return {"error": f"Ollama request failed: {e}", "suggestions": [], "suggestionCount": 0, "raw": ""}

    suggestions = []
    current: dict = {}

    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("SUGGESTION:"):
            if current.get("suggestion"):
                suggestions.append(current)
            current = {"suggestion": line.replace("SUGGESTION:", "").strip()}
        elif line.startswith("ROOTED_IN:") and current:
            current["rootedIn"] = line.replace("ROOTED_IN:", "").strip()
        elif line.startswith("FITS_BECAUSE:") and current:
            current["fitsBecause"] = line.replace("FITS_BECAUSE:", "").strip()

    if current.get("suggestion"):
        suggestions.append(current)

    return {
        "suggestions":     suggestions,
        "suggestionCount": len(suggestions),
        "raw":             raw,
    }
