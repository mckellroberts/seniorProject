"""
Writing Agent — orchestrator
Routes requests to the appropriate specialized sub-agent and manages the
per-profile cache so only stale or missing analyses are re-run.
Uncached analyses are executed concurrently.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ..tools.vectorStore import ChromaRetriever

# Analysis agents
from .sentenceAnalyzer   import analyzeSentences
from .vocabularyAnalyzer import analyzeVocabulary
from .toneAnalyzer       import analyzeTone
from .storyDetector      import detectStoryPatterns
from .characterProfiler  import profileCharacters
from .plotTracker        import trackPlot
from .paragraphAnalyzer  import analyzeParagraphs

# Generation agents
from .voiceGenerator    import generateInVoice, generateInVoiceStream
from .ideaGenerator     import generateIdeas
from .stuckAgent        import getUnstuckSuggestions
from .continuationAgent import continueWriting as _continueWriting
from .sceneAgent        import draftScene as _draftScene
from .dialogueAgent     import writeDialogue as _writeDialogue

# Cache
from .profileCache import (
    computeFingerprint, loadProfile, saveProfile,
    loadGeneration, saveGeneration,
)

_CACHE_DIR_NAME = "cache"

# Maps cache key → analysis function. Order doesn't matter; they run concurrently.
_ANALYSIS_AGENTS: list[tuple[str, callable]] = [
    ("sentenceProfile",   analyzeSentences),
    ("vocabularyProfile", analyzeVocabulary),
    ("toneProfile",       analyzeTone),
    ("storyPatterns",     detectStoryPatterns),
    ("paragraphStats",    analyzeParagraphs),
    ("characterProfiles", profileCharacters),
    ("plotSummary",       trackPlot),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cacheDir(vectorStoreDir: Path) -> Path:
    return vectorStoreDir.parent / _CACHE_DIR_NAME


def _assembleStyleProfile(sentenceProfile: dict, vocabularyProfile: dict, toneProfile: dict) -> dict:
    return {
        "sentences":  sentenceProfile,
        "vocabulary": vocabularyProfile,
        "tone":       toneProfile,
    }


def _getProfiles(
    retriever: ChromaRetriever,
    userId: str,
    vectorStoreDir: Path,
) -> tuple[dict, dict, dict, dict, dict, dict, dict]:
    """
    Return all seven analysis profiles.

    Each profile is loaded from cache individually. Only profiles whose
    fingerprint has changed (or was never cached) are re-run, and those
    are executed concurrently via a thread pool.

    Returns:
        (styleProfile, storyPatterns, paragraphStats, characterProfiles,
         plotSummary, sentenceProfile, vocabularyProfile)
    """
    docCount    = retriever.count()
    sources     = retriever.listSources()
    fingerprint = computeFingerprint(docCount, sources)
    cacheDir    = _cacheDir(vectorStoreDir)

    # Load whatever is already cached
    cached: dict[str, dict] = {}
    missing: list[tuple[str, callable]] = []

    for key, fn in _ANALYSIS_AGENTS:
        profile = loadProfile(cacheDir, userId, fingerprint, key)
        if profile is not None:
            cached[key] = profile
        else:
            missing.append((key, fn))

    # Run only missing analyses, concurrently
    if missing:
        with ThreadPoolExecutor(max_workers=len(missing)) as pool:
            futures = {pool.submit(fn, retriever): key for key, fn in missing}
            for future in as_completed(futures):
                key  = futures[future]
                data = future.result()
                cached[key] = data
                saveProfile(cacheDir, userId, fingerprint, key, data)

    styleProfile = _assembleStyleProfile(
        cached["sentenceProfile"],
        cached["vocabularyProfile"],
        cached["toneProfile"],
    )
    return (
        styleProfile,
        cached["storyPatterns"],
        cached["paragraphStats"],
        cached["characterProfiles"],
        cached["plotSummary"],
        cached["sentenceProfile"],
        cached["vocabularyProfile"],
    )


def _requireRetriever(userId: str, vectorStoreDir: Path) -> ChromaRetriever | None:
    retriever = ChromaRetriever(persistDirectory=vectorStoreDir, userId=userId)
    return retriever if retriever.count() > 0 else None


_NO_SAMPLES = {"error": "No writing samples uploaded yet. Please upload some of your work first."}


# ── Public entry points ───────────────────────────────────────────────────────

def buildStyleProfile(
    retriever: ChromaRetriever,
    userId: str = "default",
    vectorStoreDir: Path | None = None,
) -> dict:
    """Return the full style profile. Called from the /styleProfile Flask route."""
    if vectorStoreDir is not None:
        styleProfile, _, _, _, _, _, _ = _getProfiles(retriever, userId, vectorStoreDir)
        return styleProfile
    return _assembleStyleProfile(
        analyzeSentences(retriever),
        analyzeVocabulary(retriever),
        analyzeTone(retriever),
    )


def generateInUserVoice(
    prompt: str,
    userId: str,
    vectorStoreDir: Path,
    styleHint: str = "",
) -> dict:
    """General-purpose generation in the user's voice. Called from Flask /generate."""
    retriever = _requireRetriever(userId, vectorStoreDir)
    if retriever is None:
        return {**_NO_SAMPLES, "generatedText": None, "styleProfile": None,
                "storyPatterns": None, "sourcesUsed": []}

    cacheDir    = _cacheDir(vectorStoreDir)
    fingerprint = computeFingerprint(retriever.count(), retriever.listSources())

    cached = loadGeneration(cacheDir, userId, fingerprint, prompt, extra=styleHint)
    if cached is not None:
        return cached

    styleProfile, storyPatterns, paragraphStats, _, _, _, _ = _getProfiles(
        retriever, userId, vectorStoreDir
    )
    generation = generateInVoice(
        prompt=prompt,
        retriever=retriever,
        styleProfile=styleProfile,
        storyPatterns=storyPatterns,
        styleHint=styleHint,
    )
    result = {
        "generatedText":  generation.get("generatedText"),
        "styleProfile":   styleProfile,
        "storyPatterns":  storyPatterns,
        "paragraphStats": paragraphStats,
        "sourcesUsed":    generation.get("sourcesUsed", []),
        **({ "error": generation["error"] } if "error" in generation else {}),
    }
    if generation.get("generatedText"):
        saveGeneration(cacheDir, userId, fingerprint, prompt, result, extra=styleHint)
    return result


def streamInUserVoice(
    prompt: str,
    userId: str,
    vectorStoreDir: Path,
    styleHint: str = "",
):
    """
    Streaming generation in the user's voice.
    Yields dicts: {"text": "..."} for each chunk, {"error": "..."} on failure.
    Profiles are loaded from cache (or computed) before streaming begins.
    """
    retriever = _requireRetriever(userId, vectorStoreDir)
    if retriever is None:
        yield {"error": _NO_SAMPLES["error"]}
        return

    styleProfile, storyPatterns, _, _, _, _, _ = _getProfiles(retriever, userId, vectorStoreDir)

    try:
        full_text = []
        for chunk in generateInVoiceStream(
            prompt=prompt,
            retriever=retriever,
            styleProfile=styleProfile,
            storyPatterns=storyPatterns,
            styleHint=styleHint,
        ):
            if "error" in chunk:
                yield chunk
                return
            yield chunk
            full_text.append(chunk["text"])

        # Cache the completed result so the next identical request is instant
        if full_text:
            cacheDir    = _cacheDir(vectorStoreDir)
            fingerprint = computeFingerprint(retriever.count(), retriever.listSources())
            saveGeneration(
                cacheDir, userId, fingerprint, prompt,
                {"generatedText": "".join(full_text), "sourcesUsed": chunk.get("sources", [])},
                extra=styleHint,
            )
    except Exception as e:
        yield {"error": f"Ollama request failed: {e}"}


def continueWriting(lastParagraph: str, userId: str, vectorStoreDir: Path) -> dict:
    """Continue the story from the writer's last paragraph. Called from Flask /continue."""
    retriever = _requireRetriever(userId, vectorStoreDir)
    if retriever is None:
        return {**_NO_SAMPLES, "continuation": None, "sourcesUsed": []}

    cacheDir    = _cacheDir(vectorStoreDir)
    fingerprint = computeFingerprint(retriever.count(), retriever.listSources())

    cached = loadGeneration(cacheDir, userId, fingerprint, lastParagraph, extra="continue")
    if cached is not None:
        return cached

    styleProfile, storyPatterns, _, characterProfiles, _, _, _ = _getProfiles(
        retriever, userId, vectorStoreDir
    )
    result = _continueWriting(
        lastParagraph=lastParagraph,
        retriever=retriever,
        styleProfile=styleProfile,
        storyPatterns=storyPatterns,
        characterProfiles=characterProfiles,
    )
    if result.get("continuation"):
        saveGeneration(cacheDir, userId, fingerprint, lastParagraph, result, extra="continue")
    return result


def getUnstuck(
    userId: str,
    vectorStoreDir: Path,
    context: str = "",
    count: int = 3,
) -> dict:
    """Return story-grounded suggestions for a stuck writer. Called from Flask /unstuck."""
    retriever = _requireRetriever(userId, vectorStoreDir)
    if retriever is None:
        return {**_NO_SAMPLES, "suggestions": [], "suggestionCount": 0}

    styleProfile, storyPatterns, _, characterProfiles, plotSummary, _, _ = _getProfiles(
        retriever, userId, vectorStoreDir
    )
    return getUnstuckSuggestions(
        retriever=retriever,
        styleProfile=styleProfile,
        storyPatterns=storyPatterns,
        characterProfiles=characterProfiles,
        plotSummary=plotSummary,
        context=context,
        count=count,
    )


def writeScene(
    prompt: str,
    userId: str,
    vectorStoreDir: Path,
    characters: list[str] | None = None,
    location: str = "",
    mood: str = "",
) -> dict:
    """Draft a scene in the author's voice. Called from Flask /scene."""
    retriever = _requireRetriever(userId, vectorStoreDir)
    if retriever is None:
        return {**_NO_SAMPLES, "scene": None, "sourcesUsed": []}

    styleProfile, storyPatterns, _, characterProfiles, _, _, _ = _getProfiles(
        retriever, userId, vectorStoreDir
    )
    return _draftScene(
        prompt=prompt,
        retriever=retriever,
        styleProfile=styleProfile,
        storyPatterns=storyPatterns,
        characterProfiles=characterProfiles,
        characters=characters,
        location=location,
        mood=mood,
    )


def writeDialogue(
    context: str,
    userId: str,
    vectorStoreDir: Path,
    characters: list[str] | None = None,
) -> dict:
    """Write dialogue between characters in the author's voice. Called from Flask /dialogue."""
    retriever = _requireRetriever(userId, vectorStoreDir)
    if retriever is None:
        return {**_NO_SAMPLES, "dialogue": None, "sourcesUsed": []}

    styleProfile, _, _, characterProfiles, _, _, _ = _getProfiles(
        retriever, userId, vectorStoreDir
    )
    return _writeDialogue(
        context=context,
        retriever=retriever,
        styleProfile=styleProfile,
        characterProfiles=characterProfiles,
        characters=characters,
    )


def getWritingIdeas(
    userId: str,
    vectorStoreDir: Path,
    topic: str = "",
    count: int = 5,
) -> dict:
    """Return story ideas tailored to the user's style. Called from Flask /ideas."""
    retriever = _requireRetriever(userId, vectorStoreDir)
    if retriever is None:
        return {**_NO_SAMPLES, "ideas": [], "ideaCount": 0}

    return generateIdeas(retriever=retriever, topic=topic, count=count)
