"""
Profile Cache
Persists style profiles and story patterns per user so they don't need
to be re-analyzed on every generation request.

Invalidation strategy: compare the number of chunks currently in the
vector store against what was recorded when the cache was written.
Any upload or deletion changes the count, which busts the cache.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

CACHE_DIR_NAME = "cache"


def _cachePath(cacheDir: Path, userId: str) -> Path:
    return cacheDir / f"{userId}_profile.json"


def loadCache(cacheDir: Path, userId: str, currentDocCount: int) -> dict | None:
    """
    Return cached profiles if they are still valid, otherwise None.

    Args:
        cacheDir:        Directory where cache files are stored.
        userId:          User whose cache to load.
        currentDocCount: Current number of chunks in the vector store.

    Returns:
        dict with keys styleProfile, storyPatterns — or None if stale/missing.
    """
    path = _cachePath(cacheDir, userId)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    if data.get("docCount") != currentDocCount:
        return None

    return {
        "styleProfile":   data["styleProfile"],
        "storyPatterns":  data["storyPatterns"],
        "paragraphStats": data["paragraphStats"],
    }


def saveCache(
    cacheDir: Path,
    userId: str,
    styleProfile: dict,
    storyPatterns: dict,
    paragraphStats: dict,
    currentDocCount: int,
) -> None:
    """
    Write profiles to disk.

    Args:
        cacheDir:        Directory where cache files are stored.
        userId:          User whose cache to write.
        styleProfile:    Output from analyzeStyle.
        storyPatterns:   Output from detectStoryPatterns.
        paragraphStats:  Output from analyzeParagraphs.
        currentDocCount: Number of chunks in the vector store right now.
    """
    cacheDir.mkdir(parents=True, exist_ok=True)
    data = {
        "styleProfile":   styleProfile,
        "storyPatterns":  storyPatterns,
        "paragraphStats": paragraphStats,
        "docCount":       currentDocCount,
        "cachedAt":       datetime.now(timezone.utc).isoformat(),
    }
    _cachePath(cacheDir, userId).write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def invalidateCache(cacheDir: Path, userId: str) -> None:
    """
    Explicitly delete a user's cache file.
    Useful if you ever need to force a re-analysis without changing doc count.
    """
    path = _cachePath(cacheDir, userId)
    if path.exists():
        path.unlink()
