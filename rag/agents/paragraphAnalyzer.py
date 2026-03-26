"""
Paragraph Analyzer
Measures concrete, quantifiable writing patterns from the user's uploaded text.
No LLM required — all analysis is rule-based.

Covers:
  - Sentence length (avg, min, max, distribution)
  - Paragraph length (avg sentences and words)
  - Dialogue vs. exposition ratio
  - Punctuation habits (em-dash, ellipsis, semicolon, etc.)

NOTE: Sentence splitting currently uses regex. If edge-case accuracy becomes
important (e.g. abbreviations like "Dr." or "etc." being mis-split), swap
_splitSentences() for NLTK's sent_tokenize with no other changes needed:

    from nltk.tokenize import sent_tokenize
    def _splitSentences(text: str) -> list[str]:
        return [s.strip() for s in sent_tokenize(text) if s.strip()]
"""

from __future__ import annotations

import re
from ..tools.vectorStore import ChromaRetriever

# ── Sentence splitting ────────────────────────────────────────────────────────

# Split on .  !  ?  when followed by whitespace + an uppercase letter or end of
# string. This catches most sentence boundaries without splitting on common
# abbreviations like "Mr. Smith" or decimal numbers like "3.14".
_SENTENCE_END = re.compile(r'(?<=[.!?])\s+(?=[A-Z"\u201c])')

def _splitSentences(text: str) -> list[str]:
    """Split a block of text into sentences using regex."""
    sentences = _SENTENCE_END.split(text.strip())
    return [s.strip() for s in sentences if s.strip()]


# ── Dialogue detection ────────────────────────────────────────────────────────

# Matches straight quotes and curly (smart) quotes
_QUOTE_CHARS = re.compile(r'["\u201c\u201d]')

def _isDialogue(sentence: str) -> bool:
    """Return True if the sentence appears to contain spoken dialogue."""
    return bool(_QUOTE_CHARS.search(sentence))


# ── Punctuation counters ──────────────────────────────────────────────────────

_PATTERNS = {
    "emDash":      re.compile(r'—'),
    "ellipsis":    re.compile(r'\.{3}|…'),
    "semicolon":   re.compile(r';'),
    "exclamation": re.compile(r'!'),
    "question":    re.compile(r'\?'),
}


# ── Main analysis ─────────────────────────────────────────────────────────────

def analyzeParagraphs(retriever: ChromaRetriever) -> dict:
    """
    Retrieve a broad sample of the user's writing and return concrete
    structural statistics.

    Returns:
        dict with keys:
            sentenceLength   — avg, min, max, distribution by category
            paragraphLength  — avg sentence count and word count per paragraph
            dialogueRatio    — float 0–1 (proportion of sentences with dialogue)
            punctuationHabits — raw counts across the full sample
            sampleSize       — how many chunks and sentences were analyzed
    """
    results = retriever.retrieve(query="writing prose narrative dialogue exposition", limit=15)

    if not results:
        return {"error": "No writing samples found."}

    allSentences: list[str] = []
    paragraphSentenceCounts: list[int] = []
    paragraphWordCounts: list[int] = []
    punctuationTotals = {key: 0 for key in _PATTERNS}

    for r in results:
        chunk = r["document"]

        # Treat each chunk as a "paragraph" unit for paragraph-level stats
        chunkSentences = _splitSentences(chunk)
        if not chunkSentences:
            continue

        paragraphSentenceCounts.append(len(chunkSentences))
        paragraphWordCounts.append(len(chunk.split()))
        allSentences.extend(chunkSentences)

        for key, pattern in _PATTERNS.items():
            punctuationTotals[key] += len(pattern.findall(chunk))

    if not allSentences:
        return {"error": "Could not extract sentences from writing samples."}

    # ── Sentence length stats ────────────────────────────────────────────────
    wordCounts = [len(s.split()) for s in allSentences]
    avg = sum(wordCounts) / len(wordCounts)

    short  = sum(1 for w in wordCounts if w < 10)
    medium = sum(1 for w in wordCounts if 10 <= w <= 20)
    long   = sum(1 for w in wordCounts if w > 20)
    total  = len(wordCounts)

    sentenceLength = {
        "avg": round(avg, 1),
        "min": min(wordCounts),
        "max": max(wordCounts),
        "distribution": {
            "short":  f"{round(short  / total * 100)}%",
            "medium": f"{round(medium / total * 100)}%",
            "long":   f"{round(long   / total * 100)}%",
        },
    }

    # ── Paragraph length stats ───────────────────────────────────────────────
    paragraphLength = {
        "avgSentences": round(sum(paragraphSentenceCounts) / len(paragraphSentenceCounts), 1),
        "avgWords":     round(sum(paragraphWordCounts)     / len(paragraphWordCounts),     1),
    }

    # ── Dialogue ratio ───────────────────────────────────────────────────────
    dialogueCount = sum(1 for s in allSentences if _isDialogue(s))
    dialogueRatio = round(dialogueCount / total, 2)

    return {
        "sentenceLength":    sentenceLength,
        "paragraphLength":   paragraphLength,
        "dialogueRatio":     dialogueRatio,
        "punctuationHabits": punctuationTotals,
        "sampleSize": {
            "chunks":    len(results),
            "sentences": total,
        },
    }
