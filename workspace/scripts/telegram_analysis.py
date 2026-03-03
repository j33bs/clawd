#!/usr/bin/env python3
"""Baseline Telegram analysis utilities (opt-in, lightweight)."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("workspace/state_runtime/ingest/telegram_normalized/messages.jsonl")


def load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def analysis_enabled() -> bool:
    return str(os.environ.get("OPENCLAW_TELEGRAM_ANALYSIS", "0")).strip().lower() in {"1", "true", "yes", "on"}


def run_topics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    texts = [str(row.get("text", "")) for row in rows if str(row.get("text", "")).strip()]
    if not texts:
        return {"mode": "topics", "status": "empty"}
    try:
        from sklearn.cluster import KMeans  # type: ignore
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
    except Exception:
        return {
            "mode": "topics",
            "status": "unavailable",
            "reason": "sklearn_not_installed",
            "hint": "Install scikit-learn to enable TF-IDF + kmeans topics.",
        }

    vectorizer = TfidfVectorizer(max_features=128, stop_words="english")
    matrix = vectorizer.fit_transform(texts)
    n_clusters = min(3, max(1, len(texts)))
    model = KMeans(n_clusters=n_clusters, n_init=5, random_state=7)
    labels = model.fit_predict(matrix)
    counts = Counter(int(x) for x in labels)
    return {
        "mode": "topics",
        "status": "ok",
        "clusters": dict(sorted(counts.items())),
    }


def run_sentiment(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positive = {"thanks", "great", "awesome", "love", "nice", "good", "happy"}
    negative = {"sorry", "bad", "failed", "issue", "problem", "angry", "sad"}
    pos = 0
    neg = 0
    for row in rows:
        text = str(row.get("text", "")).lower()
        tokens = set(re.findall(r"[a-zA-Z']+", text))
        pos += sum(1 for token in tokens if token in positive)
        neg += sum(1 for token in tokens if token in negative)
    return {"mode": "sentiment", "status": "ok", "baseline": True, "positive_hits": pos, "negative_hits": neg}


def run_alignment_patterns(rows: list[dict[str, Any]]) -> dict[str, Any]:
    apology_patterns = ("sorry", "my bad", "apologies")
    certainty_patterns = ("definitely", "certainly", "always", "never")
    apology_count = 0
    certainty_count = 0
    for row in rows:
        text = str(row.get("text", "")).lower()
        apology_count += sum(1 for needle in apology_patterns if needle in text)
        certainty_count += sum(1 for needle in certainty_patterns if needle in text)
    return {
        "mode": "alignment_patterns",
        "status": "ok",
        "apology_frequency": apology_count,
        "certainty_markers": certainty_count,
    }


def run_relationship_growth(rows: list[dict[str, Any]]) -> dict[str, Any]:
    daily: dict[str, int] = {}
    for row in rows:
        ts = str(row.get("timestamp", ""))
        day = ts[:10] if len(ts) >= 10 else "unknown"
        daily[day] = daily.get(day, 0) + 1
    return {"mode": "relationship_growth", "status": "ok", "messages_per_day": dict(sorted(daily.items()))}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Telegram analysis baseline commands.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for cmd in ("topics", "sentiment", "alignment_patterns", "relationship_growth"):
        child = sub.add_parser(cmd)
        child.add_argument("--input", default=str(DEFAULT_INPUT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not analysis_enabled():
        print(
            json.dumps(
                {
                    "status": "disabled",
                    "hint": "Set OPENCLAW_TELEGRAM_ANALYSIS=1 to enable telegram_analysis commands.",
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        return 0

    rows = load_rows(Path(args.input).resolve())
    if args.cmd == "topics":
        result = run_topics(rows)
    elif args.cmd == "sentiment":
        result = run_sentiment(rows)
    elif args.cmd == "alignment_patterns":
        result = run_alignment_patterns(rows)
    else:
        result = run_relationship_growth(rows)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
