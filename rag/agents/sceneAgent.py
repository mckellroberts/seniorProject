"""
Scene Agent
Drafts a specific scene with given parameters (characters, location, mood),
written in the author's voice and consistent with established story elements.
"""

from __future__ import annotations

import requests
from ..tools.vectorStore import ChromaRetriever

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"
RAG_TOP_K    = 5


def draftScene(
    prompt: str,
    retriever: ChromaRetriever,
    styleProfile: dict,
    storyPatterns: dict,
    characterProfiles: dict,
    characters: list[str] | None = None,
    location: str = "",
    mood: str = "",
) -> dict:
    """
    Draft a scene with specific parameters in the author's voice.

    Args:
        prompt:            What happens in this scene.
        retriever:         User's ChromaRetriever.
        styleProfile:      Combined style profile (keys: sentences, vocabulary, tone).
        storyPatterns:     Narrative pattern profile.
        characterProfiles: Known characters from characterProfiler.
        characters:        Names of characters who appear in this scene.
        location:          Where the scene takes place.
        mood:              Desired emotional atmosphere.

    Returns:
        dict with keys: scene, sourcesUsed
    """
    charNames  = characters or []
    sceneQuery = " ".join(filter(None, [prompt] + charNames + [location])).strip()
    relevantChunks = retriever.retrieve(query=sceneQuery, limit=RAG_TOP_K)
    writingContext  = "\n\n---\n\n".join(r["document"] for r in relevantChunks)
    sources         = list({r["metadata"].get("source", "unknown") for r in relevantChunks})

    # Build character context from profiles for the named characters
    charContext = ""
    if charNames and characterProfiles.get("characters"):
        matched = [
            c for c in characterProfiles["characters"]
            if c.get("name", "") in charNames
        ]
        if matched:
            charContext = "\n".join(
                f"- {c['name']}: {c.get('description', '')} | Motivation: {c.get('motivation', '')}"
                for c in matched
            )

    sentenceSection   = styleProfile.get("sentences", {})
    vocabularySection = styleProfile.get("vocabulary", {})
    toneSection       = styleProfile.get("tone", {})

    rhythm      = sentenceSection.get("rhythm", "") if isinstance(sentenceSection, dict) else ""
    register    = vocabularySection.get("register", "") if isinstance(vocabularySection, dict) else ""
    fragments   = sentenceSection.get("fragmentUse", "") if isinstance(sentenceSection, dict) else ""
    primaryTone = toneSection.get("primaryTone", "") if isinstance(toneSection, dict) else ""
    pacing      = storyPatterns.get("pacing", "")
    narrativePOV = storyPatterns.get("narrativePOV", "")

    systemPrompt = (
        "You are a writing assistant drafting a scene in the author's voice. "
        "Use the character profiles and story context to stay consistent with the existing work.\n\n"
        "=== AUTHOR'S STYLE ===\n"
        f"Sentence rhythm: {rhythm}\n"
        f"Vocabulary register: {register}\n"
        f"Fragment use: {fragments}\n"
        f"Tone: {primaryTone}\n"
        f"Pacing: {pacing}\n"
        f"POV: {narrativePOV}\n\n"
        + (f"=== CHARACTERS IN THIS SCENE ===\n{charContext}\n\n" if charContext else "")
        + "=== AUTHOR'S WRITING (mirror this style) ===\n"
        f"{writingContext}"
    )

    sceneSpec = f"Scene: {prompt}"
    if location:
        sceneSpec += f"\nLocation: {location}"
    if mood:
        sceneSpec += f"\nMood/atmosphere: {mood}"
    if charNames:
        sceneSpec += f"\nCharacters present: {', '.join(charNames)}"

    userMessage = (
        f"{sceneSpec}\n\n"
        "Draft this scene in the author's voice. Write the scene directly — no preamble or explanation."
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": userMessage, "system": systemPrompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        return {
            "scene":       response.json().get("response", "").strip(),
            "sourcesUsed": sources,
        }
    except requests.RequestException as e:
        return {"error": f"Ollama request failed: {e}", "scene": None, "sourcesUsed": []}
