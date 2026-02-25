from __future__ import annotations

import argparse
import json
import math
import os
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = REPO_ROOT / "workspace"
if str(WORKSPACE_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(WORKSPACE_ROOT))

from memory_ext._common import append_jsonl, runtime_dir, utc_now_iso  # type: ignore
from memory_ext.local_rag import LocalEmbedder  # type: ignore

BASELINE = 1.0 / 7.0


def _log_path() -> Path:
    return runtime_dir("store", "being_divergence.jsonl")


def _default_sections() -> Dict[str, List[str]]:
    return {
        "c_lawd": [
            "governance gate deterministic patch verification",
            "minimal diff audit evidence and reversible change",
            "offline tests and strict preflight contracts",
        ],
        "Claude Code": [
            "implementation details for python modules and routing",
            "refactor notes for code quality and interfaces",
            "test matrix execution and fixture maintenance",
        ],
        "Grok": [
            "broad ideation with playful framing and trend synthesis",
            "high variance exploration across internet narratives",
            "fast hypothesis generation with colorful language",
        ],
        "ChatGPT": [
            "balanced assistant response with concise structure",
            "general purpose planning and explanation style",
            "practical implementation hints with safe defaults",
        ],
    }


def _mean(vectors: List[List[float]]) -> List[float]:
    if not vectors:
        return []
    dim = len(vectors[0])
    acc = [0.0] * dim
    for vec in vectors:
        if len(vec) != dim:
            continue
        for idx, val in enumerate(vec):
            acc[idx] += float(val)
    return [val / float(len(vectors)) for val in acc]


def compute_centroid(
    being_name: str,
    texts_by_being: Optional[Dict[str, List[str]]] = None,
    embedder: Optional[LocalEmbedder] = None,
) -> List[float]:
    corpus = texts_by_being or _default_sections()
    texts = corpus.get(being_name, [])
    model = embedder or LocalEmbedder(dim=64)
    vectors = [model.embed(t) for t in texts if str(t).strip()]
    return _mean(vectors)


def cosine_distance(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 1.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 1.0
    similarity = dot / (na * nb)
    return 1.0 - max(-1.0, min(1.0, similarity))


def being_divergence(
    being_a: str,
    being_b: str,
    texts_by_being: Optional[Dict[str, List[str]]] = None,
    embedder: Optional[LocalEmbedder] = None,
) -> float:
    cen_a = compute_centroid(being_a, texts_by_being=texts_by_being, embedder=embedder)
    cen_b = compute_centroid(being_b, texts_by_being=texts_by_being, embedder=embedder)
    return cosine_distance(cen_a, cen_b)


def is_significant(score: float) -> bool:
    return float(score) > BASELINE


def _log_enabled(override: Optional[bool] = None) -> bool:
    if override is not None:
        return bool(override)
    return str(os.getenv("OPENCLAW_MEMORY_EXT", "0")).strip().lower() in {"1", "true", "yes", "on"}


def run_divergence_analysis(
    texts_by_being: Optional[Dict[str, List[str]]] = None,
    enable_log: Optional[bool] = None,
) -> Dict[str, Any]:
    corpus = texts_by_being or _default_sections()
    beings = sorted(corpus.keys())
    embedder = LocalEmbedder(dim=64)
    pairs: Dict[str, float] = {}
    for a, b in combinations(beings, 2):
        key = "{a}|{b}".format(a=a, b=b)
        pairs[key] = being_divergence(a, b, texts_by_being=corpus, embedder=embedder)

    payload: Dict[str, Any] = {
        "timestamp_utc": utc_now_iso(),
        "pairs": pairs,
        "random_baseline": BASELINE,
        "significant_pairs": [k for k, v in pairs.items() if is_significant(v)],
    }

    if _log_enabled(enable_log):
        append_jsonl(_log_path(), payload)

    return payload


def _main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic being divergence analysis")
    parser.add_argument("--log", action="store_true", help="Write analysis to workspace/state_runtime/store/being_divergence.jsonl")
    args = parser.parse_args()
    result = run_divergence_analysis(enable_log=args.log)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
