from __future__ import annotations

import re

_REDACTIONS = (
    (re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]+"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+[A-Za-z0-9._-]{8,}"), "authorization: bearer [REDACTED]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._-]{16,}"), "bearer [REDACTED]"),
    (re.compile(r"(?i)\b[A-F0-9]{24,}\b"), "[REDACTED_HEX]"),
)


def redact_for_embedding(text: str) -> str:
    out = "" if text is None else str(text)
    for pattern, repl in _REDACTIONS:
        out = pattern.sub(repl, out)
    return out
