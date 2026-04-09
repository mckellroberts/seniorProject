"""
Character Profiler Agent
Extracts named characters from the writer's uploaded work — their descriptions,
roles, relationships, and behavioral traits — to ground generation in actual story people.

Response shape (success): { characters, characterCount, raw }
Response shape (error):   { error, characters, characterCount, raw }
"""

from __future__ import annotations

import requests
from ..tools.vectorStore import ChromaRetriever

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"


def profileCharacters(retriever: ChromaRetriever) -> dict:
    """
    Retrieve character-heavy samples and extract a profile for each named character.

    Returns:
        dict with keys: characters (list of dicts), characterCount, raw
    """
    characterQueries = [
        "character description appearance personality",
        "character motivation goals desires",
        "character relationship interaction dialogue",
        "character backstory history past",
    ]

    samples = []
    for query in characterQueries:
        results = retriever.retrieve(query=query, limit=2)
        for r in results:
            samples.append(r["document"])

    if not samples:
        return {"error": "No writing samples found.", "characters": [], "characterCount": 0, "raw": ""}

    seen = set()
    uniqueSamples = []
    for s in samples:
        if s not in seen:
            seen.add(s)
            uniqueSamples.append(s)

    combinedText = "\n\n---\n\n".join(uniqueSamples[:8])

    prompt = (
        "You are a story analyst. Read these writing samples and identify every named character. "
        "For each character you find, provide a concise profile.\n\n"
        "Return each character in exactly this format (repeat for each):\n"
        "CHARACTER: (name)\n"
        "ROLE: (protagonist/antagonist/supporting/minor)\n"
        "DESCRIPTION: (physical and personality traits observed in the text)\n"
        "MOTIVATION: (what drives them — goals, fears, desires)\n"
        "RELATIONSHIPS: (how they relate to other characters in the text)\n\n"
        "Only include characters who actually appear in these samples. Do not invent.\n\n"
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
        return {"error": f"Ollama request failed: {e}", "characters": [], "characterCount": 0, "raw": ""}

    characters = []
    current: dict = {}

    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("CHARACTER:"):
            if current.get("name"):
                characters.append(current)
            current = {"name": line.replace("CHARACTER:", "").strip()}
        elif line.startswith("ROLE:") and current:
            current["role"] = line.replace("ROLE:", "").strip()
        elif line.startswith("DESCRIPTION:") and current:
            current["description"] = line.replace("DESCRIPTION:", "").strip()
        elif line.startswith("MOTIVATION:") and current:
            current["motivation"] = line.replace("MOTIVATION:", "").strip()
        elif line.startswith("RELATIONSHIPS:") and current:
            current["relationships"] = line.replace("RELATIONSHIPS:", "").strip()

    if current.get("name"):
        characters.append(current)

    return {
        "characters":     characters,
        "characterCount": len(characters),
        "raw":            raw,
    }
