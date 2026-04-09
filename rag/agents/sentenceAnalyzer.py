"""
Sentence Analyzer Agent
Analyzes the rhythmic and structural patterns of the writer's sentences:
avg length, complexity, fragment use, and rhythm tendencies.

Response shape (success): { avgLength, rhythm, complexity, fragmentUse, patterns, raw }
Response shape (error):   { error, raw }
"""

from __future__ import annotations

import requests
from ..tools.vectorStore import ChromaRetriever

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"


def analyzeSentences(retriever: ChromaRetriever) -> dict:
    """
    Pull writing samples and analyze sentence-level patterns only.

    Returns:
        dict with keys: avgLength, rhythm, complexity, fragmentUse, patterns, raw
    """
    results = retriever.retrieve(query="sentence rhythm structure prose flow", limit=6)
    if not results:
        return {"error": "No writing samples found.", "raw": ""}

    combinedText = "\n\n---\n\n".join(r["document"] for r in results)

    prompt = (
        "You are a linguist analyzing sentence construction. Study these writing samples "
        "and describe only the sentence-level patterns — nothing about theme or vocabulary.\n\n"
        "Return in exactly this format:\n"
        "AVG_LENGTH: (short/medium/long — and rough word estimate per sentence)\n"
        "RHYTHM: (staccato/flowing/varied — how sentence length varies across a passage)\n"
        "COMPLEXITY: (simple/compound/complex/mixed — clause structure tendencies)\n"
        "FRAGMENTS: (yes/no/occasional — does the author use sentence fragments deliberately)\n"
        "PATTERNS: (any notable structural habits — anaphora, parallel structure, trailing clauses, etc.)\n\n"
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
        if line.startswith("AVG_LENGTH:"):
            profile["avgLength"] = line.replace("AVG_LENGTH:", "").strip()
        elif line.startswith("RHYTHM:"):
            profile["rhythm"] = line.replace("RHYTHM:", "").strip()
        elif line.startswith("COMPLEXITY:"):
            profile["complexity"] = line.replace("COMPLEXITY:", "").strip()
        elif line.startswith("FRAGMENTS:"):
            profile["fragmentUse"] = line.replace("FRAGMENTS:", "").strip()
        elif line.startswith("PATTERNS:"):
            profile["patterns"] = line.replace("PATTERNS:", "").strip()

    return profile
