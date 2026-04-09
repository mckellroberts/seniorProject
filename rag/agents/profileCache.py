"""
Profile Cache
Persists each analysis profile independently so a stale or missing profile
only triggers re-analysis for that one agent, not the full set.

Fingerprint strategy: SHA-256 of (docCount + sorted source filenames).
This catches both count changes and delete-then-reupload scenarios where
the count stays the same but the content changes.

Generation cache: LLM outputs are cached by (userId, promptHash, fingerprint)
so repeated identical requests return immediately without hitting Ollama.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

CACHE_DIR_NAME = "cache"


# ── Fingerprint ───────────────────────────────────────────────────────────────

def computeFingerprint(docCount: int, sources: list[str]) -> str:
    """
    Return a short hash representing the current state of a user's document
    collection. Used to detect when any profile cache is stale.
    """
    raw = f"{docCount}:{':'.join(sorted(sources))}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── Per-profile cache ─────────────────────────────────────────────────────────

def _profilePath(cacheDir: Path, userId: str, profileKey: str) -> Path:
    return cacheDir / f"{userId}_{profileKey}.json"


def loadProfile(cacheDir: Path, userId: str, fingerprint: str, profileKey: str) -> dict | None:
    """
    Return cached profile data if the fingerprint still matches, else None.

    Args:
        cacheDir:    Directory where cache files are stored.
        userId:      Owner of the cache.
        fingerprint: Current document fingerprint from computeFingerprint().
        profileKey:  Which profile to load (e.g. "sentenceProfile").
    """
    path = _profilePath(cacheDir, userId, profileKey)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if data.get("fingerprint") != fingerprint:
        return None
    return data.get("data")


def saveProfile(
    cacheDir: Path,
    userId: str,
    fingerprint: str,
    profileKey: str,
    data: dict,
) -> None:
    """
    Persist a single profile to disk.

    Args:
        cacheDir:    Directory where cache files are stored.
        userId:      Owner of the cache.
        fingerprint: Document fingerprint at time of analysis.
        profileKey:  Which profile to store (e.g. "sentenceProfile").
        data:        The profile dict returned by the analysis agent.
    """
    cacheDir.mkdir(parents=True, exist_ok=True)
    payload = {
        "fingerprint": fingerprint,
        "data":        data,
        "cachedAt":    datetime.now(timezone.utc).isoformat(),
    }
    _profilePath(cacheDir, userId, profileKey).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def invalidateUser(cacheDir: Path, userId: str) -> None:
    """Delete all cached profiles for a user."""
    for path in cacheDir.glob(f"{userId}_*.json"):
        path.unlink()


# Back-compat alias used by older code paths
invalidateCache = invalidateUser


# ── Generation result cache ───────────────────────────────────────────────────

def _promptHash(prompt: str, extra: str = "") -> str:
    """Short hash of a prompt string (+ optional extra context like styleHint)."""
    raw = f"{prompt}:{extra}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _generationPath(cacheDir: Path, userId: str, promptHash: str) -> Path:
    return cacheDir / f"{userId}_gen_{promptHash}.json"


def loadGeneration(
    cacheDir: Path,
    userId: str,
    fingerprint: str,
    prompt: str,
    extra: str = "",
) -> dict | None:
    """
    Return a cached generation result if the fingerprint still matches.

    Args:
        cacheDir:    Directory where cache files are stored.
        userId:      Owner of the cache.
        fingerprint: Current document fingerprint from computeFingerprint().
        prompt:      The generation prompt text.
        extra:       Any additional input (e.g. styleHint) that affects output.
    """
    ph   = _promptHash(prompt, extra)
    path = _generationPath(cacheDir, userId, ph)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if data.get("fingerprint") != fingerprint:
        return None
    return data.get("result")


def saveGeneration(
    cacheDir: Path,
    userId: str,
    fingerprint: str,
    prompt: str,
    result: dict,
    extra: str = "",
) -> None:
    """
    Persist a generation result to disk.

    Args:
        cacheDir:    Directory where cache files are stored.
        userId:      Owner of the cache.
        fingerprint: Document fingerprint at time of generation.
        prompt:      The prompt that produced this result.
        result:      The dict returned by the generation agent.
        extra:       Any additional input that was part of the request.
    """
    cacheDir.mkdir(parents=True, exist_ok=True)
    ph      = _promptHash(prompt, extra)
    payload = {
        "fingerprint": fingerprint,
        "result":      result,
        "cachedAt":    datetime.now(timezone.utc).isoformat(),
    }
    _generationPath(cacheDir, userId, ph).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
