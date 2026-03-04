"""Non-intrusive CEL cache hook surface.

This module intentionally exposes integration points only.
"""

from __future__ import annotations

from typing import Any


def register_embedding_cache(cache_backend: Any | None = None, **kwargs: Any) -> dict[str, Any]:
    """Register embedding cache backend metadata without enabling heavy caching."""
    return {
        "ok": True,
        "hook": "embedding_cache",
        "enabled": cache_backend is not None,
        "backend": type(cache_backend).__name__ if cache_backend is not None else None,
        "options": dict(kwargs),
    }


def register_result_cache(cache_backend: Any | None = None, **kwargs: Any) -> dict[str, Any]:
    """Register result cache backend metadata without enabling heavy caching."""
    return {
        "ok": True,
        "hook": "result_cache",
        "enabled": cache_backend is not None,
        "backend": type(cache_backend).__name__ if cache_backend is not None else None,
        "options": dict(kwargs),
    }
