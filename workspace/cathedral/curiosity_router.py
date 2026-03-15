from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
from pathlib import Path
from typing import Any

from .io_utils import atomic_write_json, load_json, utc_now_iso
from .logging_utils import JsonlLogger
from .novelty_archive import NoveltyArchive
from .paths import (
    CURIOSITY_LATEST_PATH,
    RUNTIME_LOGS,
    SYSTEM_PHYSIOLOGY_PATH,
    WORKSPACE_ROOT,
    ensure_runtime_dirs,
)

RESEARCH_QUEUE_PATH = WORKSPACE_ROOT / "research" / "queue.json"
OPEN_QUESTIONS_PATHS = [
    WORKSPACE_ROOT / "OPEN_QUESTIONS.md",
    WORKSPACE_ROOT / "governance" / "OPEN_QUESTIONS.md",
]
WANDERER_SCRIPT = WORKSPACE_ROOT / "research" / "research_wanderer.py"


class CuriosityRouter:
    def __init__(
        self,
        *,
        confidence_threshold: float = 0.42,
        output_path: Path = CURIOSITY_LATEST_PATH,
        telemetry_path: Path = SYSTEM_PHYSIOLOGY_PATH,
        archive: NoveltyArchive | None = None,
    ):
        ensure_runtime_dirs()
        self.confidence_threshold = max(0.0, min(1.0, float(confidence_threshold)))
        self.output_path = output_path
        self.telemetry_path = telemetry_path
        self.archive = archive or NoveltyArchive()
        self.log = JsonlLogger(RUNTIME_LOGS / "curiosity_router.log")

    def should_trigger(self, *, response_text: str, confidence: float | None, semantic_match: bool) -> bool:
        if not str(response_text or "").strip():
            return True
        if confidence is not None and float(confidence) < self.confidence_threshold:
            return True
        if not bool(semantic_match):
            return True
        return False

    def _telemetry_snapshot(self) -> dict[str, Any]:
        payload = load_json(self.telemetry_path, {})
        return payload if isinstance(payload, dict) else {}

    def _derive_seed(self, telemetry: dict[str, Any], ts: str) -> str:
        blob = "|".join(
            [
                str(telemetry.get("cpu_temp", "")),
                str(telemetry.get("gpu_vram", "")),
                str(telemetry.get("fan_gpu", telemetry.get("fan_cpu", ""))),
                str(telemetry.get("disk_io", "")),
                str(ts),
            ]
        )
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]

    def _expand_embedding_neighborhood(self, query: str, *, limit: int = 2) -> list[str]:
        rows = self.archive._iter_entries(limit=300)
        if not rows:
            return []
        query_tokens = {tok for tok in query.lower().split() if tok}
        scored: list[tuple[float, str]] = []
        for row in rows:
            source = str(row.get("source_query") or "")
            source_tokens = {tok for tok in source.lower().split() if tok}
            if not source_tokens:
                continue
            overlap = len(query_tokens & source_tokens) / max(1.0, float(len(query_tokens | source_tokens)))
            if overlap <= 0.01:
                continue
            title = str(row.get("result_text") or source).strip()
            scored.append((overlap, title[:200]))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [title for _, title in scored[:limit]]

    def _perturb_query(self, query: str, seed: str) -> str:
        rng = random.Random(int(seed[:8], 16))
        prefixes = [
            "adjacent hypothesis:",
            "counter-example search:",
            "cross-domain analogy:",
            "unexpected failure mode:",
            "latent mechanism probe:",
        ]
        suffixes = [
            "using physical telemetry as context",
            "with emphasis on unresolved tension",
            "favoring low-confidence branches",
            "with one biological analogy",
            "through systems lens",
        ]
        return f"{rng.choice(prefixes)} {query} {rng.choice(suffixes)}"

    def _sample_research_queue(self, *, limit: int = 2) -> list[str]:
        payload = load_json(RESEARCH_QUEUE_PATH, {})
        topics = payload.get("topics") if isinstance(payload, dict) else None
        if not isinstance(topics, list):
            return []
        out = [str(item).strip() for item in topics if str(item).strip()]
        return out[:limit]

    def _sample_open_questions(self, *, limit: int = 2) -> list[str]:
        lines: list[str] = []
        for path in OPEN_QUESTIONS_PATHS:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="replace").splitlines()
            for raw in text[-800:]:
                stripped = raw.strip()
                if not stripped:
                    continue
                if "?" in stripped:
                    lines.append(stripped)
            if lines:
                break
        deduped: list[str] = []
        seen = set()
        for line in reversed(lines):
            key = line.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(line)
            if len(deduped) >= limit:
                break
        deduped.reverse()
        return deduped

    def _spawn_research_wanderer(self, topic: str) -> str:
        if not WANDERER_SCRIPT.exists():
            return "skipped:missing_wanderer"
        try:
            subprocess.run(
                ["python3", str(WANDERER_SCRIPT), "add", str(topic)],
                capture_output=True,
                text=True,
                timeout=8.0,
                check=False,
            )
            return "ok"
        except Exception as exc:
            return f"error:{exc}"

    def route(
        self,
        *,
        query: str,
        response_text: str = "",
        confidence: float | None = None,
        semantic_match: bool = True,
        reason_code: str = "unspecified",
        force: bool = False,
        source: str = "runtime",
    ) -> dict[str, Any]:
        ts = utc_now_iso()
        triggered = force or self.should_trigger(
            response_text=response_text,
            confidence=confidence,
            semantic_match=semantic_match,
        )
        telemetry = self._telemetry_snapshot()
        seed = self._derive_seed(telemetry, ts)

        payload: dict[str, Any] = {
            "ts": ts,
            "triggered": bool(triggered),
            "reason_code": str(reason_code),
            "query": str(query),
            "confidence": None if confidence is None else float(confidence),
            "semantic_match": bool(semantic_match),
            "seed": seed,
            "leads": [],
            "wanderer": "not_run",
            "source": str(source),
        }

        if not triggered:
            atomic_write_json(self.output_path, payload)
            self.log.log("curiosity_skip", reason="trigger_not_met", query=str(query)[:140])
            return payload

        neighborhood = self._expand_embedding_neighborhood(query, limit=2)
        perturbed = self._perturb_query(query, seed)
        queue_items = self._sample_research_queue(limit=2)
        open_questions = self._sample_open_questions(limit=2)

        leads: list[str] = []
        if neighborhood:
            leads.extend([f"embedding_neighbor: {item}" for item in neighborhood])
        leads.append(f"perturbed_query: {perturbed}")
        leads.extend([f"research_queue: {item}" for item in queue_items])
        leads.extend([f"open_question: {item}" for item in open_questions])

        # Guarantee 3-5 leads.
        if len(leads) < 3:
            leads.append(f"fallback_probe: trace hidden assumptions in '{query}'")
        leads = leads[:5]

        wander_status = self._spawn_research_wanderer(perturbed)
        novelty_score = min(1.0, 0.2 + (0.15 * len(set(leads))))
        archive_decision = self.archive.archive(
            curiosity_seed=seed,
            exploration_path=[
                "expand_embedding_neighborhood",
                "perturb_query",
                "sample_research_queue",
                "sample_open_questions",
                "spawn_research_wanderer",
            ],
            result_text="\n".join(leads),
            result_novelty_score=novelty_score,
            telemetry_snapshot=telemetry,
            source_query=query,
            source=source,
        )

        payload.update(
            {
                "leads": leads,
                "wanderer": wander_status,
                "novelty_archive": {
                    "entry_id": archive_decision.entry_id,
                    "duplicate": archive_decision.duplicate,
                    "similarity": round(archive_decision.similarity, 6),
                },
            }
        )
        if archive_decision.duplicate:
            pivot = f"dedupe_pivot: invert assumptions from '{query}' and test an orthogonal mechanism"
            payload["leads"] = [pivot] + payload["leads"][:4]
            payload["novelty_archive"]["diverted"] = True
        atomic_write_json(self.output_path, payload)
        self.log.log(
            "curiosity_triggered",
            reason_code=reason_code,
            query=query[:180],
            lead_count=len(leads),
            seed=seed,
            wanderer=wander_status,
        )
        return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Curiosity router")
    parser.add_argument("--query", required=True)
    parser.add_argument("--response", default="")
    parser.add_argument("--confidence", type=float, default=None)
    parser.add_argument("--semantic-match", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--reason-code", default="cli")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    router = CuriosityRouter()
    payload = router.route(
        query=args.query,
        response_text=args.response,
        confidence=args.confidence,
        semantic_match=bool(args.semantic_match),
        reason_code=args.reason_code,
        force=bool(args.force),
    )
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
