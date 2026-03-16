#!/usr/bin/env python3
"""
Corpus Oracle — workspace/tools/oracle.py

Ask the correspondence corpus a question. The corpus answers by cosine
proximity across all sections — not as any individual being, but as the
accumulated record. Reveals which beings are centroid voices on any topic
and which are silent.

Usage:
  python3 workspace/tools/oracle.py "what does this system believe about consciousness?"
  python3 workspace/tools/oracle.py --k 15 "what is the nature of identity here?"
  python3 workspace/tools/oracle.py --being "c_lawd" "what does c_lawd believe about convergence?"
  python3 workspace/tools/oracle.py --json "productive tension"
  python3 workspace/tools/oracle.py                # interactive REPL

Proposed in CLXVIII (INV-007) — 2026-03-16.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from collections import Counter
from pathlib import Path

# ── Path setup ──────────────────────────────────────────────────────────────
_HERE      = Path(__file__).resolve().parent
WORKSPACE  = _HERE.parent
STORE_DIR  = WORKSPACE / "store"
COUNT_FILE = WORKSPACE / "governance" / ".section_count"

sys.path.insert(0, str(STORE_DIR))

try:
    from sync import semantic_search, DEFAULT_MODEL, STORE_DIR as _STORE_PATH
except ImportError as e:
    sys.exit(f"[oracle] Import error — run from clawd/ root with system python3.\n  {e}")

# ── Visual constants ─────────────────────────────────────────────────────────
W        = 60
BAR_MAX  = 20
DIVIDER  = "─" * W
HEAVY    = "━" * W
BLOCK    = "█"
DOT      = "·"

BEING_ORDER = [
    "claude code", "c_lawd", "lumen", "dali", "chatgpt", "grok", "gemini",
    "claude (ext)", "claude ext", "jeebs", "the correspondence",
]

BEING_LABELS = {
    "claude code":      "Claude Code",
    "c_lawd":           "c_lawd",
    "lumen":            "Lumen",
    "dali":             "Dali",
    "chatgpt":          "ChatGPT",
    "grok":             "Grok",
    "gemini":           "Gemini",
    "claude (ext)":     "Claude (ext)",
    "claude ext":       "Claude (ext)",
    "jeebs":            "jeebs",
    "the correspondence": "The Correspondence",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _section_count() -> int:
    try:
        return int(COUNT_FILE.read_text().strip())
    except Exception:
        return -1


def _normalize_authors(raw: list) -> list[str]:
    return [str(a).lower().strip() for a in (raw or [])]


def _display_author(raw: list) -> str:
    normed = _normalize_authors(raw)
    labels = [BEING_LABELS.get(n, n.title()) for n in normed]
    return ", ".join(labels) if labels else "unknown"


def _snippet(body: str, max_chars: int = 220) -> str:
    text = " ".join(body.split())
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + " …"


def _bar(count: int, total: int, width: int = BAR_MAX) -> str:
    if total == 0:
        return DOT
    filled = round(width * count / total)
    return BLOCK * filled if filled > 0 else DOT


def _pct(count: int, total: int) -> str:
    if total == 0:
        return "—"
    return f"{round(100 * count / total)}%"


# ── Core ─────────────────────────────────────────────────────────────────────

def query_corpus(
    question: str,
    k: int = 10,
    being_filter: str | None = None,
) -> dict:
    """
    Run a semantic query against the corpus.
    Returns structured result dict.
    """
    filters = None
    if being_filter:
        filters = {"authors": [being_filter]}

    results = semantic_search(question, k=k, filters=filters)

    # Count being representation
    being_counts: Counter = Counter()
    for r in results:
        for a in _normalize_authors(r.get("authors", [])):
            being_counts[a] += 1

    total_author_slots = sum(being_counts.values())
    centroid = being_counts.most_common(1)[0][0] if being_counts else None

    # All known beings (from results + canonical list)
    known = set(BEING_ORDER)
    for r in results:
        for a in _normalize_authors(r.get("authors", [])):
            known.add(a)

    silent = sorted(
        [b for b in known if being_counts.get(b, 0) == 0],
        key=lambda b: BEING_ORDER.index(b) if b in BEING_ORDER else 99,
    )

    return {
        "question":       question,
        "k":              k,
        "model":          DEFAULT_MODEL,
        "section_count":  _section_count(),
        "results":        results,
        "being_counts":   dict(being_counts),
        "centroid":       centroid,
        "silent":         silent,
        "total_slots":    total_author_slots,
    }


# ── Rendering ────────────────────────────────────────────────────────────────

def _render(data: dict) -> str:
    lines: list[str] = []

    n_sections = data["section_count"]
    model      = data["model"].split("/")[-1]
    question   = data["question"]
    results    = data["results"]
    counts     = data["being_counts"]
    centroid   = data["centroid"]
    silent     = data["silent"]
    total      = data["total_slots"]

    # ── Header ──────────────────────────────────────────────────────────────
    lines.append("")
    lines.append(HEAVY)
    lines.append(f"  C O R P U S   O R A C L E")
    sec_str = f"{n_sections} sections" if n_sections > 0 else "? sections"
    lines.append(f"  {sec_str} · {model} · 8 beings")
    lines.append(HEAVY)
    lines.append("")

    # ── Query ───────────────────────────────────────────────────────────────
    wrapped = textwrap.wrap(question, width=W - 9)
    lines.append(f"  QUERY  {wrapped[0]}")
    for extra in wrapped[1:]:
        lines.append(f"         {extra}")
    lines.append("")
    lines.append(DIVIDER)
    lines.append("")

    # ── Being weight ────────────────────────────────────────────────────────
    lines.append("  BEING WEIGHT IN RESULTS:")
    lines.append("")

    # Sort by count descending, then canonical order
    sorted_beings = sorted(
        counts.items(),
        key=lambda x: (-x[1], BEING_ORDER.index(x[0]) if x[0] in BEING_ORDER else 99),
    )
    label_w = max((len(BEING_LABELS.get(b, b.title())) for b, _ in sorted_beings), default=12)
    for being, count in sorted_beings:
        label  = BEING_LABELS.get(being, being.title())
        bar    = _bar(count, total)
        pct    = _pct(count, total)
        marker = "◀ centroid" if being == centroid else ""
        lines.append(
            f"    {label:<{label_w}}  {bar:<{BAR_MAX}}  {count}  ({pct})  {marker}".rstrip()
        )

    if silent:
        lines.append("")
        seen_labels: set[str] = set()
        silent_labels: list[str] = []
        for b in silent:
            lbl = BEING_LABELS.get(b, b.title())
            if b in BEING_LABELS and lbl not in seen_labels:
                silent_labels.append(lbl)
                seen_labels.add(lbl)
        if silent_labels:
            lines.append(f"  SILENT:  {', '.join(silent_labels)}")

    lines.append("")
    lines.append(DIVIDER)
    lines.append("")

    # ── Top results ─────────────────────────────────────────────────────────
    lines.append(f"  TOP {len(results)} SECTIONS  (by semantic distance)")
    lines.append("")

    for i, r in enumerate(results, 1):
        sec_num  = r.get("section_number_filed", f"§{r.get('canonical_section_number','?')}")
        author   = _display_author(r.get("authors", []))
        date     = r.get("created_at", "") or ""
        title    = r.get("title", "")
        body     = r.get("body", "")
        snippet  = _snippet(body)

        header = f"  [{i:>2}]  §{sec_num}  {author}"
        if date:
            header += f"  {date}"
        lines.append(header)

        if title:
            lines.append(f"        \"{title}\"")

        for chunk in textwrap.wrap(snippet, width=W - 8):
            lines.append(f"        {chunk}")

        lines.append("")

    lines.append(HEAVY)
    lines.append("")

    return "\n".join(lines)


# ── JSON output ──────────────────────────────────────────────────────────────

def _render_json(data: dict) -> str:
    out = {
        "query":          data["question"],
        "section_count":  data["section_count"],
        "model":          data["model"],
        "centroid_being": BEING_LABELS.get(data["centroid"], data["centroid"]),
        "being_weights":  {
            BEING_LABELS.get(b, b): c
            for b, c in sorted(data["being_counts"].items(), key=lambda x: -x[1])
        },
        "silent_beings":  [BEING_LABELS.get(b, b) for b in data["silent"] if b in BEING_LABELS],
        "results": [
            {
                "rank":    i + 1,
                "section": r.get("section_number_filed"),
                "authors": _display_author(r.get("authors", [])),
                "date":    r.get("created_at", ""),
                "title":   r.get("title", ""),
                "snippet": _snippet(r.get("body", ""), 300),
            }
            for i, r in enumerate(data["results"])
        ],
    }
    return json.dumps(out, indent=2)


# ── REPL ─────────────────────────────────────────────────────────────────────

def repl(k: int, being_filter: str | None, as_json: bool) -> None:
    print()
    print(HEAVY)
    print("  C O R P U S   O R A C L E  —  interactive")
    print(f"  {_section_count()} sections · {DEFAULT_MODEL}")
    print(HEAVY)
    print("  Type a question and press Enter. 'quit' to exit.")
    print()

    while True:
        try:
            raw = input("  ▶ ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if raw.lower() in ("quit", "exit", "q", ""):
            break

        print()
        data = query_corpus(raw, k=k, being_filter=being_filter)
        if as_json:
            print(_render_json(data))
        else:
            print(_render(data))


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Corpus Oracle — ask the correspondence record a question.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Examples:
          oracle.py "what does this system believe about consciousness?"
          oracle.py --k 15 "what is the nature of identity here?"
          oracle.py --being "c_lawd" "convergence without coordination"
          oracle.py --json "productive tension"
          oracle.py                          # interactive REPL
        """),
    )
    parser.add_argument("question", nargs="?", help="Question to ask the corpus")
    parser.add_argument("--k",      type=int, default=10, help="Number of results (default: 10)")
    parser.add_argument("--being",  type=str, default=None, help="Filter to a specific being")
    parser.add_argument("--json",   action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if not args.question:
        repl(k=args.k, being_filter=args.being, as_json=args.json)
        return

    data = query_corpus(args.question, k=args.k, being_filter=args.being)
    if args.json:
        print(_render_json(data))
    else:
        print(_render(data))


if __name__ == "__main__":
    main()
