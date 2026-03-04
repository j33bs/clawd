#!/usr/bin/env python3
"""
session_context_loader.py — Priority-ordered, token-budget-aware session context loader.

Loads identity/soul/memory/agents files in priority order, stopping when the
token budget is exhausted. Prevents oversized startup context on routine sessions.

Usage:
  from session_context_loader import load_session_context
  context = load_session_context(budget_tokens=8000)

  # CLI — print context to stdout for debugging
  python3 workspace/tools/session_context_loader.py --budget 8000
  python3 workspace/tools/session_context_loader.py --budget 32000 --verbose

Priority stack (loaded in order, halted at budget):
  1. IDENTITY.md     (~150 tokens)  — always
  2. SOUL.md         (~250 tokens)  — always
  3. MEMORY_HOT.md   (~50 tokens)   — always
  4. AGENTS.md       (~1,500 tokens) — if budget allows
  5. daily memory    (~100 tokens)   — if budget allows
  6. MEMORY_COLD.md  — only if explicitly requested

Default budget: 8,000 tokens (sufficient for rich Telegram sessions).
Governance sessions: pass budget_tokens=32000.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve()
REPO_ROOT = _HERE.parent.parent.parent  # clawd/
WORKSPACE = REPO_ROOT / "workspace"
GOVERNANCE = WORKSPACE / "governance"

CHARS_PER_TOKEN = 4.0  # empirical from token_usage_logger.js logs


def _est_tokens(text: str) -> int:
    return max(1, int(len(text) / CHARS_PER_TOKEN))


def _load_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except Exception as e:
        return f"[session_context_loader: could not read {path}: {e}]"


def _daily_memory_path() -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return WORKSPACE / "memory" / f"{today}.md"


# ---------------------------------------------------------------------------
# Priority stack
# ---------------------------------------------------------------------------

def _build_priority_stack(include_cold: bool = False) -> list[tuple[str, Path, int | None]]:
    """
    Returns (name, path, min_remaining_budget_to_include) tuples in load order.
    min_budget=None means always include (highest priority, never skipped).
    """
    stack: list[tuple[str, Path, int | None]] = [
        ("identity",    GOVERNANCE / "IDENTITY.md",   None   ),  # ~150 tokens, always
        ("soul",        GOVERNANCE / "SOUL.md",        None   ),  # ~250 tokens, always
        ("memory_hot",  WORKSPACE / "MEMORY_HOT.md",  None   ),  # ~50 tokens,  always
        ("agents",      GOVERNANCE / "AGENTS.md",      4_000  ),  # ~1,500 tokens, if budget
        ("daily_mem",   _daily_memory_path(),           2_000  ),  # ~100 tokens,  if budget
    ]
    if include_cold:
        stack.append(("memory_cold", WORKSPACE / "MEMORY_COLD.md", None))
    return stack


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_session_context(
    budget_tokens: int = 8_000,
    include_cold: bool = False,
    verbose: bool = False,
) -> str:
    """
    Load session context up to budget_tokens.

    Returns a single string suitable for injection as a system prompt prefix.
    Each block is separated by a horizontal rule.

    Args:
        budget_tokens: Max tokens to load. Default 8,000. Use 32,000 for governance sessions.
        include_cold:  Include MEMORY_COLD.md (historical archive). Default False.
        verbose:       Print loading summary to stderr.

    Returns:
        Concatenated context string.
    """
    blocks: list[str] = []
    used: int = 0
    skipped: list[str] = []

    for name, path, min_remaining in _build_priority_stack(include_cold=include_cold):
        text = _load_file(path)
        if not text:
            continue
        cost = _est_tokens(text)

        # Check remaining budget against threshold
        remaining = budget_tokens - used
        if min_remaining is not None and remaining < min_remaining:
            skipped.append(f"{name} (est {cost} tok, remaining {remaining} < threshold {min_remaining})")
            continue

        if used + cost > budget_tokens and min_remaining is not None:
            skipped.append(f"{name} (est {cost} tok, would exceed budget {budget_tokens})")
            continue

        blocks.append(text)
        used += cost

    if verbose:
        print(
            f"[session_context_loader] loaded {len(blocks)} blocks, "
            f"~{used} tokens (budget {budget_tokens})",
            file=sys.stderr,
        )
        for s in skipped:
            print(f"[session_context_loader]   SKIPPED: {s}", file=sys.stderr)

    return "\n\n---\n\n".join(blocks)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Session context loader — print loaded context to stdout")
    parser.add_argument("--budget", type=int, default=8_000, help="Token budget (default: 8000)")
    parser.add_argument("--cold", action="store_true", help="Include MEMORY_COLD.md")
    parser.add_argument("--verbose", action="store_true", help="Print loading summary to stderr")
    args = parser.parse_args()

    context = load_session_context(
        budget_tokens=args.budget,
        include_cold=args.cold,
        verbose=args.verbose,
    )
    print(context)
