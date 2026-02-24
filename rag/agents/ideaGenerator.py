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
        return {"error": "No writing samples found. Please upload some of your work first."}

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

    response = requests.post(
        OLLAMA_URL,
        json={"model": OLLAMA_MODEL, "prompt": ideaPrompt, "stream": False},
    )
    response.raise_for_status()
    raw = response.json().get("response", "").strip()

    # Parse ideas out of the structured response
    ideas = []
    currentIdea: dict = {}

    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("IDEA:"):
            if currentIdea:
                ideas.append(currentIdea)
            currentIdea = {"idea": line.replace("IDEA:", "").strip()}
        elif line.startswith("HOOK:") and currentIdea:
            currentIdea["hook"] = line.replace("HOOK:", "").strip()
        elif line.startswith("FIT:") and currentIdea:
            currentIdea["fit"] = line.replace("FIT:", "").strip()

    if currentIdea:
        ideas.append(currentIdea)

    return {
        "ideas":     ideas,
        "ideaCount": len(ideas),
        "topic":     topic or "open",
        "raw":       raw,
    }