"""
Story Detector Agent
Analyzes the user's uploaded writing to identify narrative patterns,
story arc preferences, common themes, and structural habits.
"""

from __future__ import annotations

import requests
from ..tools.vectorStore import ChromaRetriever

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"


def detectStoryPatterns(retriever: ChromaRetriever) -> dict:
    """
    Retrieve narrative samples and analyze story structure, themes,
    and arc patterns the author tends to use.

    Returns:
        dict with keys: arcType, themes, pacing, conflictStyle, narrativePOV, raw
    """
    # Pull samples that are most likely to contain narrative structure
    narrativeQueries = [
        "story conflict and tension",
        "character motivation and arc",
        "plot structure beginning middle end",
        "narrative climax or resolution",
    ]

    samples = []
    for query in narrativeQueries:
        results = retriever.retrieve(query=query, limit=2)
        for r in results:
            samples.append(r["document"])

    if not samples:
        return {"error": "No writing samples found. Please upload some of your work first."}

    # Deduplicate while preserving order
    seen = set()
    uniqueSamples = []
    for s in samples:
        if s not in seen:
            seen.add(s)
            uniqueSamples.append(s)

    combinedText = "\n\n---\n\n".join(uniqueSamples[:8])

    detectionPrompt = (
        "You are a narrative analyst. Study these writing samples and identify the author's "
        "storytelling patterns. Be specific and grounded in what you actually see in the text.\n\n"
        "Return your analysis in exactly this format:\n"
        "ARC: (what story arc structure do they favor — hero's journey, in medias res, slice of life, etc.)\n"
        "THEMES: (recurring themes or subject matter — loss, identity, redemption, etc.)\n"
        "PACING: (fast/slow, action-heavy/introspective, scene vs summary balance)\n"
        "CONFLICT: (internal vs external conflict, how tension is built and released)\n"
        "POV: (point of view tendencies — first/third person, close/distant, reliable/unreliable)\n\n"
        f"WRITING SAMPLES:\n{combinedText}"
    )

    response = requests.post(
        OLLAMA_URL,
        json={"model": OLLAMA_MODEL, "prompt": detectionPrompt, "stream": False},
    )
    response.raise_for_status()
    raw = response.json().get("response", "").strip()

    patterns = {"raw": raw}
    for line in raw.splitlines():
        if line.startswith("ARC:"):
            patterns["arcType"] = line.replace("ARC:", "").strip()
        elif line.startswith("THEMES:"):
            patterns["themes"] = line.replace("THEMES:", "").strip()
        elif line.startswith("PACING:"):
            patterns["pacing"] = line.replace("PACING:", "").strip()
        elif line.startswith("CONFLICT:"):
            patterns["conflictStyle"] = line.replace("CONFLICT:", "").strip()
        elif line.startswith("POV:"):
            patterns["narrativePOV"] = line.replace("POV:", "").strip()

    return patterns