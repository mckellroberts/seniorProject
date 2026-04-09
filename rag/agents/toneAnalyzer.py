"""
Tone Analyzer Agent
Identifies the emotional register, mood patterns, atmospheric tendencies,
and tone shifts in the writer's work.

Response shape (success): { primaryTone, toneRange, emotionalDepth, atmosphericWords, toneShifts, raw }
Response shape (error):   { error, raw }
"""

from __future__ import annotations

import requests
from ..tools.vectorStore import ChromaRetriever

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"


def analyzeTone(retriever: ChromaRetriever) -> dict:
    """
    Pull emotionally charged samples and analyze tone patterns only.

    Returns:
        dict with keys: primaryTone, toneRange, emotionalDepth, atmosphericWords, toneShifts, raw
    """
    results = retriever.retrieve(query="emotion mood atmosphere feeling tension", limit=6)
    if not results:
        return {"error": "No writing samples found.", "raw": ""}

    combinedText = "\n\n---\n\n".join(r["document"] for r in results)

    prompt = (
        "You are an emotional intelligence analyst studying creative writing. Analyze the tone "
        "and emotional qualities in these samples — nothing about sentence structure or vocabulary.\n\n"
        "Return in exactly this format:\n"
        "PRIMARY_TONE: (the dominant emotional register — dark/hopeful/sardonic/melancholic/etc.)\n"
        "TONE_RANGE: (narrow/wide — does the author stay in one register or shift frequently)\n"
        "EMOTIONAL_DEPTH: (surface/moderate/deep — how much interiority or emotion the author explores)\n"
        "ATMOSPHERIC_WORDS: (words or images the author uses to set emotional atmosphere)\n"
        "TONE_SHIFTS: (how and when the author shifts tone — gradual/abrupt/via dialogue/etc.)\n\n"
        f"WRITING SAMPLES:\n{combinedText}"
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        raw = response.json().get("response", "").strip()
    except requests.RequestException as e:
        return {"error": f"Ollama request failed: {e}", "raw": ""}

    profile = {"raw": raw}
    for line in raw.splitlines():
        if line.startswith("PRIMARY_TONE:"):
            profile["primaryTone"] = line.replace("PRIMARY_TONE:", "").strip()
        elif line.startswith("TONE_RANGE:"):
            profile["toneRange"] = line.replace("TONE_RANGE:", "").strip()
        elif line.startswith("EMOTIONAL_DEPTH:"):
            profile["emotionalDepth"] = line.replace("EMOTIONAL_DEPTH:", "").strip()
        elif line.startswith("ATMOSPHERIC_WORDS:"):
            profile["atmosphericWords"] = line.replace("ATMOSPHERIC_WORDS:", "").strip()
        elif line.startswith("TONE_SHIFTS:"):
            profile["toneShifts"] = line.replace("TONE_SHIFTS:", "").strip()

    return profile
