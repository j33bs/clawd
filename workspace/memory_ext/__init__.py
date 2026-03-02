"""Memory extension package (feature-gated).

Set OPENCLAW_MEMORY_EXT=1 to enable. When disabled, this package exports
no-op stubs for pre_response_hook and relationship_hook so callers can
import unconditionally without activating the extension modules.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

_ENABLED = os.getenv("OPENCLAW_MEMORY_EXT", "0") not in ("", "0", "false", "False")

if _ENABLED:
    from .hooks import pre_response_hook, relationship_hook  # full implementations
else:
    def pre_response_hook(  # type: ignore[misc]
        text: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """No-op stub — OPENCLAW_MEMORY_EXT not enabled."""
        return {}

    def relationship_hook(  # type: ignore[misc]
        text: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """No-op stub — OPENCLAW_MEMORY_EXT not enabled."""
        return {}

__all__ = ["pre_response_hook", "relationship_hook"]
