"""
Body sanitizer for CorrespondenceStore embedding input.

Strips governance tags and status phrases before vectorization to prevent
tag-Goodharting (XCII requirement: "sanitization to prevent tag-Goodharting").

RULE: Sanitization is applied to the body BEFORE embedding.
      It NEVER modifies the stored body field — only the embedding input.

Tags stripped:
  [EXEC:*]   — executive attribution tags
  [JOINT:*]  — jointly-signed output markers
  [UPPER:*]  — upper-layer attribution markers
  Status phrases (see STATUS_PHRASES below)

Version bumped when patterns or phrases change — must be logged in audit output.
"""
from __future__ import annotations
import re

# ── version ──────────────────────────────────────────────────────────────────
SANITIZER_VERSION = "1.0.0"

# ── tag patterns ─────────────────────────────────────────────────────────────
_TAG_PATTERN = re.compile(
    r"\[(EXEC|JOINT|UPPER):[^\]]*\]",
    re.IGNORECASE,
)

# ── status phrases ────────────────────────────────────────────────────────────
# Phrases that are governance artefacts, not semantic content.
# Keep this list minimal — only phrases that are mechanically inserted by
# the governance protocol and would bias embedding toward procedural tokens.
STATUS_PHRASES: list[str] = [
    "GATE-INV004-PASS",
    "GATE-INV004-REJECTION",
    "isolation_verified: true",
    "isolation_verified: false",
    "isolation_evidence",
    "embed_model:",
    "embed_version:",
    "sanitizer_version:",
    "baseline_recalibrated: true",
    "baseline_recalibrated: false",
]

_STATUS_PATTERN = re.compile(
    "|".join(re.escape(p) for p in STATUS_PHRASES),
    re.IGNORECASE,
)

# ── public API ────────────────────────────────────────────────────────────────

def sanitize(text: str) -> str:
    """
    Return text with governance tags and status phrases removed.
    Collapses resulting whitespace to single spaces.
    Does NOT modify the original text object.
    """
    cleaned = _TAG_PATTERN.sub(" ", text)
    cleaned = _STATUS_PATTERN.sub(" ", cleaned)
    # collapse whitespace
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def sanitizer_version() -> str:
    """Return the current sanitizer version string for audit logs."""
    return SANITIZER_VERSION


def diff(original: str, sanitized: str) -> dict:
    """
    Return a summary of what was removed, for audit purposes.
    Does not log secrets; only logs counts and matched tag names.
    """
    tags_removed = _TAG_PATTERN.findall(original)
    phrases_removed = _STATUS_PATTERN.findall(original)
    chars_removed = len(original) - len(sanitized)
    return {
        "tags_removed": tags_removed,
        "status_phrases_removed": phrases_removed,
        "chars_removed": chars_removed,
        "sanitizer_version": SANITIZER_VERSION,
    }
