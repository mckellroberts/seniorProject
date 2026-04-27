"""
Vocabulary Analyzer Agent
Examines the writer's word choice: register, complexity, recurring diction,
pet words, and vocabulary tendencies.

Response shape (success): { register, complexity, petWords, diction, avoidances, raw }
Response shape (error):   { error, raw }
"""

from __future__ import annotations

import requests
from ..tools.vectorStore import ChromaRetriever

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"


def analyzeVocabulary(retriever: ChromaRetriever) -> dict:
    """
    Pull writing samples and analyze vocabulary and word-choice patterns.

    Returns:
        dict with keys: register, complexity, petWords, diction, avoidances, raw
    """
    results = retriever.retrieve(query="word choice diction vocabulary language", limit=6)
    if not results:
        return {"error": "No writing samples found.", "raw": ""}

    combinedText = "\n\n---\n\n".join(r["document"] for r in results)

    prompt = (
        "You are a lexicographer analyzing an author's vocabulary. Study these writing samples "
        "and describe only vocabulary and word-choice patterns — nothing about sentence structure or theme.\n\n"
        "Return in exactly this format:\n"
        "REGISTER: (formal/informal/literary/colloquial/mixed)\n"
        "COMPLEXITY: (simple/intermediate/elevated — typical reading level)\n"
        "PET_WORDS: (words or phrases the author returns to repeatedly)\n"
        "DICTION: (concrete vs. abstract, sensory vs. conceptual, any notable tendencies)\n"
        "AVOIDANCES: (word types or registers this author seems to avoid)\n\n"
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
    profile["register"]   = _extract("REGISTER",   raw)
    profile["complexity"] = _extract("COMPLEXITY", raw)
    profile["petWords"]   = _extract("PET_WORDS",  raw) or _extract("PET WORDS", raw)
    profile["diction"]    = _extract("DICTION",    raw)
    profile["avoidances"] = _extract("AVOIDANCES", raw)

    return profile
