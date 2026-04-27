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

    import re

    def _extract(label: str, text: str) -> str:
        pattern = rf"^\*{{0,2}}{re.escape(label)}\*{{0,2}}\s*:?\s*"
        for line in text.splitlines():
            cleaned = re.sub(pattern, "", line.strip(), flags=re.IGNORECASE).strip()
            if cleaned and re.match(pattern, line.strip(), re.IGNORECASE):
                return cleaned
        return ""

    profile = {"raw": raw}
    profile["primaryTone"]      = _extract("PRIMARY_TONE",      raw) or _extract("PRIMARY TONE",      raw)
    profile["toneRange"]        = _extract("TONE_RANGE",        raw) or _extract("TONE RANGE",        raw)
    profile["emotionalDepth"]   = _extract("EMOTIONAL_DEPTH",   raw) or _extract("EMOTIONAL DEPTH",   raw)
    profile["atmosphericWords"] = _extract("ATMOSPHERIC_WORDS", raw) or _extract("ATMOSPHERIC WORDS", raw)
    profile["toneShifts"]       = _extract("TONE_SHIFTS",       raw) or _extract("TONE SHIFTS",       raw)

    return profile
