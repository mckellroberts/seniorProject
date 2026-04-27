"""
Idea Generator Agent
Generates writing ideas, prompts, and story seeds that are tailored to
the user's established style and narrative patterns.
"""

from __future__ import annotations

import requests
import os
from ..tools.vectorStore import ChromaRetriever

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"


def generateIdeas(
    retriever: ChromaRetriever,
    topic: str = "",
    count: int = 5,
) -> dict:
    """
    Generate writing ideas rooted in the user's style and story patterns.

    Args:
        retriever: The user's personal ChromaRetriever instance.
        topic:     Optional seed topic or genre to guide ideation.
        count:     How many ideas to generate (default 5).

    Returns:
        dict with keys: ideas (list of dicts), styleNote, raw
    """
    # Pull a style-representative sample to ground the ideas
    styleResults  = retriever.retrieve(query="distinctive writing style and voice", limit=3)
    themeResults  = retriever.retrieve(query="recurring themes and subject matter", limit=3)

    styleSamples  = "\n\n---\n\n".join(r["document"] for r in styleResults)
    themeSamples  = "\n\n---\n\n".join(r["document"] for r in themeResults)

    if not styleSamples:
        return {"error": "No writing samples found. Please upload some of your work first.",
                "ideas": [], "ideaCount": 0, "topic": topic or "open", "raw": ""}

    topicLine = f"The ideas should relate to or explore: {topic}\n" if topic else ""

    ideaPrompt = (
        "You are a creative writing coach. Based on these writing samples, generate "
        f"{count} specific, compelling story ideas that this author would actually want to write — "
        "ideas that fit their natural voice, themes, and strengths.\n\n"
        f"{topicLine}"
        "Return each idea in exactly this format (repeat for each idea):\n"
        "IDEA: (one sentence logline)\n"
        "HOOK: (what makes it interesting or emotionally resonant)\n"
        "FIT: (why it suits this author's style specifically)\n\n"
        f"STYLE SAMPLES:\n{styleSamples}\n\n"
        f"THEME SAMPLES:\n{themeSamples}"
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": ideaPrompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        raw = response.json().get("response", "").strip()
        print(f"[ideaGenerator] raw response ({len(raw)} chars):\n{raw[:500]}", flush=True)
    except requests.RequestException as e:
        return {"error": f"Ollama request failed: {e}",
                "ideas": [], "ideaCount": 0, "topic": topic or "open", "raw": ""}

    # Parse ideas — handle variations like **IDEA:**, "1. IDEA:", lowercase, etc.
    import re

    ideas = []
    currentIdea: dict = {}

    def _stripLabel(line: str, label: str) -> str:
        """Remove a label prefix (with optional markdown, numbers, punctuation)."""
        pattern = rf"^[\*\d\.\s]*\*{{0,2}}{label}\*{{0,2}}\s*:?\s*"
        return re.sub(pattern, "", line, flags=re.IGNORECASE).strip()

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        upper = line.upper().lstrip("*0123456789. ")
        if upper.startswith("IDEA"):
            if currentIdea:
                ideas.append(currentIdea)
            currentIdea = {"idea": _stripLabel(line, "IDEA")}
        elif upper.startswith("HOOK") and currentIdea:
            currentIdea["hook"] = _stripLabel(line, "HOOK")
        elif upper.startswith("FIT") and currentIdea:
            currentIdea["fit"] = _stripLabel(line, "FIT")

    if currentIdea:
        ideas.append(currentIdea)

    # If the model ignored the format entirely, surface the raw text as one idea
    if not ideas and raw:
        ideas = [{"idea": raw[:300], "hook": "", "fit": ""}]

    return {
        "ideas":     ideas,
        "ideaCount": len(ideas),
        "topic":     topic or "open",
        "raw":       raw,
    }