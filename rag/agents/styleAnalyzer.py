"""
Style Analyzer Agent
Examines the user's uploaded writing and extracts a detailed style profile
covering sentence structure, vocabulary, tone, and distinctive habits.
"""

from __future__ import annotations

import requests
from ..tools.vectorStore import ChromaRetriever

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"


def analyzeStyle(retriever: ChromaRetriever) -> dict:
    """
    Pull writing samples across multiple style dimensions and return a
    structured style profile.

    Returns:
        dict with keys: summary, sentenceStyle, vocabulary, tone, distinctiveHabits
    """
    # Query different aspects of writing style separately for better coverage
    aspects = {
        "sentenceStyle":     "sentence length, rhythm, and structure",
        "vocabulary":        "word choice, vocabulary level, and diction",
        "tone":              "emotional tone, mood, and atmosphere",
        "distinctiveHabits": "unusual patterns, recurring phrases, or stylistic quirks",
    }

    aspectSamples = {}
    for key, query in aspects.items():
        results = retriever.retrieve(query=query, limit=3)
        aspectSamples[key] = "\n\n---\n\n".join(r["document"] for r in results)

    # Build a combined sample for the overall summary
    allSamples = retriever.retrieve(query="writing style prose narrative", limit=6)
    combinedText = "\n\n---\n\n".join(r["document"] for r in allSamples)

    if not combinedText.strip():
        return {"error": "No writing samples found. Please upload some of your work first."}

    # Ask the model to analyze each dimension
    analysisPrompt = (
        "You are a professional literary analyst. Analyze the writing style of the author "
        "who wrote these samples. Be specific — avoid vague descriptors like 'engaging' or 'vivid'.\n\n"
        "Return your analysis in exactly this format:\n"
        "SUMMARY: (2-3 sentence overall style description)\n"
        "SENTENCES: (how they structure sentences — length, complexity, rhythm)\n"
        "VOCABULARY: (word choice tendencies — formal/casual, simple/complex, any pet words)\n"
        "TONE: (emotional register — dark, hopeful, sardonic, etc. — with examples)\n"
        "HABITS: (distinctive quirks — repetition, fragmented sentences, heavy dialogue, etc.)\n\n"
        f"WRITING SAMPLES:\n{combinedText}"
    )

    response = requests.post(
        OLLAMA_URL,
        json={"model": OLLAMA_MODEL, "prompt": analysisPrompt, "stream": False},
    )
    response.raise_for_status()
    raw = response.json().get("response", "").strip()

    # Parse the structured response into a dict
    profile = {"raw": raw}
    for line in raw.splitlines():
        if line.startswith("SUMMARY:"):
            profile["summary"] = line.replace("SUMMARY:", "").strip()
        elif line.startswith("SENTENCES:"):
            profile["sentenceStyle"] = line.replace("SENTENCES:", "").strip()
        elif line.startswith("VOCABULARY:"):
            profile["vocabulary"] = line.replace("VOCABULARY:", "").strip()
        elif line.startswith("TONE:"):
            profile["tone"] = line.replace("TONE:", "").strip()
        elif line.startswith("HABITS:"):
            profile["distinctiveHabits"] = line.replace("HABITS:", "").strip()

    return profile