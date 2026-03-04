#!/usr/bin/env python3
"""
triage_cache.py — Session-scoped task classification result cache.

The task-triage classifier runs 4-8 times per complex session on tasks that
often share the same semantic fingerprint. Caching by content hash eliminates
redundant calls (~110-240 tokens each).

Usage:
  from triage_cache import classify_with_cache

  result = classify_with_cache(task="write a function...", context="python project")
  # Returns: {"tier_suggestion": "LOCAL", "confidence": 0.95, "rationale": "..."}

  # Clear the cache (e.g. between sessions):
  clear_cache()

Controlled by:
  OPENCLAW_TRIAGE_CACHE=0  — disable caching (default: enabled)
  OPENCLAW_TRIAGE_CACHE_TTL=1800  — TTL in seconds (default: 30 minutes)
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_ENABLED = os.getenv("OPENCLAW_TRIAGE_CACHE", "1") not in ("0", "false", "False")
_TTL_S: int = int(os.getenv("OPENCLAW_TRIAGE_CACHE_TTL", "1800"))  # 30 minutes

# In-process cache: {hash: (result_dict, timestamp)}
_CACHE: dict[str, tuple[dict[str, Any], float]] = {}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_key(task: str, context: str) -> str:
    """Stable content hash for (task, context) pair."""
    payload = f"{task[:200]}|{context[:100]}"
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def _is_fresh(ts: float) -> bool:
    return (time.time() - ts) < _TTL_S


# ---------------------------------------------------------------------------
# Classifier runner (stub — replace with actual classifier call)
# ---------------------------------------------------------------------------

def _run_classifier(task: str, context: str) -> dict[str, Any]:
    """
    Run the real task-triage classifier.
    Calls workspace/skills/task-triage via mlx-infer subprocess if available.
    Falls back to a LOCAL stub when the classifier is not installed.
    """
    skill_dir = Path(__file__).parent.parent / "skills" / "task-triage"
    prompt_file = skill_dir / "config" / "classifier_prompt.md"

    if not prompt_file.exists():
        # Fallback — classifier not installed
        return {
            "tier_suggestion": "LOCAL",
            "confidence": 0.5,
            "rationale": "Classifier not available; defaulting to LOCAL.",
            "_cache_miss": True,
            "_fallback": True,
        }

    try:
        template = prompt_file.read_text(encoding="utf-8")
        filled = template.replace("{{TASK}}", task[:500]).replace("{{CONTEXT}}", context[:200])

        result = subprocess.run(
            ["mlx-infer", "--temperature", "0.1", "--max-tokens", "300"],
            input=filled,
            capture_output=True,
            text=True,
            timeout=30,
        )
        raw = result.stdout.strip()
        # Parse the first JSON object in the output
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(raw[start:end])
            parsed["_cache_miss"] = True
            return parsed
    except Exception as e:
        pass  # fall through to fallback

    return {
        "tier_suggestion": "LOCAL",
        "confidence": 0.4,
        "rationale": f"Classifier call failed; defaulting to LOCAL.",
        "_cache_miss": True,
        "_fallback": True,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_with_cache(task: str, context: str = "") -> dict[str, Any]:
    """
    Classify a task using the triage classifier, with session-scoped caching.

    Cache hit: returns cached result with _cache_hit=True, 0 tokens consumed.
    Cache miss: runs classifier, caches result, returns with _cache_miss=True.

    Args:
        task:    Task description string.
        context: Optional context string (project name, file type, etc.)

    Returns:
        dict with keys: tier_suggestion, confidence, rationale,
                        _cache_hit (on hit) or _cache_miss (on miss).
    """
    if not _ENABLED:
        return _run_classifier(task, context)

    key = _make_key(task, context)
    if key in _CACHE:
        result, ts = _CACHE[key]
        if _is_fresh(ts):
            return {**result, "_cache_hit": True}

    result = _run_classifier(task, context)
    _CACHE[key] = (result, time.time())
    return result


def clear_cache() -> None:
    """Clear all cached triage results (call between sessions if needed)."""
    _CACHE.clear()


def cache_stats() -> dict[str, int]:
    """Return cache size and number of fresh entries."""
    now = time.time()
    fresh = sum(1 for _, ts in _CACHE.values() if (now - ts) < _TTL_S)
    return {"total": len(_CACHE), "fresh": fresh, "stale": len(_CACHE) - fresh}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Task triage cache test")
    parser.add_argument("--task", default="write a hello world function in python")
    parser.add_argument("--context", default="python project")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    if args.stats:
        print(json.dumps(cache_stats(), indent=2))
    else:
        r1 = classify_with_cache(args.task, args.context)
        print("First call:", json.dumps(r1, indent=2))
        r2 = classify_with_cache(args.task, args.context)
        print("Second call (should be cache hit):", json.dumps(r2, indent=2))
