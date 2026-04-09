"""
Plot Tracker Agent
Reads the writer's uploaded work and identifies the actual story events:
major beats, setting, open threads, and current narrative state.

Response shape (success): { majorEvents, setting, openThreads, currentState, raw }
Response shape (error):   { error, raw }
"""

from __future__ import annotations

import requests
from ..tools.vectorStore import ChromaRetriever

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"


def trackPlot(retriever: ChromaRetriever) -> dict:
    """
    Retrieve narrative samples and extract concrete plot information.

    Returns:
        dict with keys: majorEvents, setting, openThreads, currentState, raw
    """
    plotQueries = [
        "story events plot what happened",
        "setting location time place world",
        "unresolved conflict open question mystery",
        "most recent scene current situation",
    ]

    samples = []
    for query in plotQueries:
        results = retriever.retrieve(query=query, limit=2)
        for r in results:
            samples.append(r["document"])

    if not samples:
        return {"error": "No writing samples found.", "raw": ""}

    seen = set()
    uniqueSamples = []
    for s in samples:
        if s not in seen:
            seen.add(s)
            uniqueSamples.append(s)

    combinedText = "\n\n---\n\n".join(uniqueSamples[:8])

    prompt = (
        "You are a story analyst. Read these writing samples and identify the concrete narrative facts "
        "— the actual events, places, and unresolved threads. Be specific to what is in the text.\n\n"
        "Return in exactly this format:\n"
        "MAJOR_EVENTS: (bullet list of the key plot events that have occurred, in rough order)\n"
        "SETTING: (where and when the story takes place)\n"
        "OPEN_THREADS: (unresolved conflicts, mysteries, or questions still in play)\n"
        "CURRENT_STATE: (where the story appears to be right now — the most recent narrative moment)\n\n"
        "Only describe what is actually in the text. Do not invent.\n\n"
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

    summary = {"raw": raw}
    for line in raw.splitlines():
        if line.startswith("MAJOR_EVENTS:"):
            summary["majorEvents"] = line.replace("MAJOR_EVENTS:", "").strip()
        elif line.startswith("SETTING:"):
            summary["setting"] = line.replace("SETTING:", "").strip()
        elif line.startswith("OPEN_THREADS:"):
            summary["openThreads"] = line.replace("OPEN_THREADS:", "").strip()
        elif line.startswith("CURRENT_STATE:"):
            summary["currentState"] = line.replace("CURRENT_STATE:", "").strip()

    return summary
