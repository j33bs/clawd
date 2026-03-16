from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from threading import Event
from typing import Any

from .io_utils import atomic_write_json, clamp01, load_json, utc_now_iso
from .logging_utils import JsonlLogger
from .paths import (
    RUNTIME_LOGS,
    TACTI_STATE_MIRROR_PATH,
    TACTI_STATE_PATH,
    WORKSPACE_ROOT,
    ensure_runtime_dirs,
)

AROUSAL_STATE_PATH = WORKSPACE_ROOT / "state_runtime" / "memory" / "arousal_state.json"
TACTI_EVENTS_PATH = WORKSPACE_ROOT / "state" / "tacti_cr" / "events.jsonl"
ROUTER_EVENTS_PATH = WORKSPACE_ROOT.parents[0] / "itc" / "llm_router_events.jsonl"
OPEN_QUESTIONS_PATH = WORKSPACE_ROOT / "OPEN_QUESTIONS.md"
RESEARCH_QUEUE_PATH = WORKSPACE_ROOT / "research" / "queue.json"
RESEARCH_FINDINGS_PATH = WORKSPACE_ROOT / "research" / "findings.json"
TRAILS_PATH = WORKSPACE_ROOT / "hivemind" / "hivemind" / "data" / "trails.jsonl"


def _tail_jsonl(path: Path, max_lines: int = 600) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out: list[dict[str, Any]] = []
    for raw in lines[-max_lines:]:
        text = raw.strip()
        if not text:
            continue
        try:
            item = json.loads(text)
        except Exception:
            continue
        if isinstance(item, dict):
            out.append(item)
    return out


def _arousal_scalar() -> float:
    payload = load_json(AROUSAL_STATE_PATH, {})
    sessions = payload.get("sessions") if isinstance(payload, dict) else None
    if not isinstance(sessions, dict) or not sessions:
        return 0.5
    values = []
    for row in sessions.values():
        if isinstance(row, dict) and isinstance(row.get("arousal"), (int, float)):
            values.append(float(row["arousal"]))
    if not values:
        return 0.5
    return clamp01(sum(values) / len(values))


def _active_agents() -> list[str]:
    rows = _tail_jsonl(TACTI_EVENTS_PATH, max_lines=500)
    ids: set[str] = set()
    for row in rows:
        session_id = row.get("session_id")
        if isinstance(session_id, str) and session_id.strip():
            ids.add(session_id.strip())
        payload = row.get("payload")
        if isinstance(payload, dict):
            for key in ("agent", "agent_id", "provider"):
                val = payload.get(key)
                if isinstance(val, str) and val.strip():
                    ids.add(val.strip())
    out = sorted(ids)
    return out[:16]


def _token_flux() -> float:
    rows = _tail_jsonl(ROUTER_EVENTS_PATH, max_lines=800)
    if not rows:
        return 0.0
    weighted = 0.0
    for row in rows:
        detail = row.get("detail") if isinstance(row.get("detail"), dict) else row
        latency = detail.get("latency_ms") if isinstance(detail, dict) else None
        attempts = detail.get("attempt") if isinstance(detail, dict) else None
        score = 0.0
        if isinstance(latency, (int, float)):
            score += min(1.0, float(latency) / 1200.0)
        if isinstance(attempts, (int, float)):
            score += min(1.0, float(attempts) / 4.0)
        reason = str(detail.get("reason_code") if isinstance(detail, dict) else "")
        if reason in {"success", "response_invalid", "response_null"}:
            score += 0.1
        weighted += score
    return clamp01(weighted / max(1.0, float(len(rows)) * 1.6))


def _memory_recall_density() -> float:
    rows = _tail_jsonl(TRAILS_PATH, max_lines=600)
    if not rows:
        return 0.0
    non_empty = 0
    referenced = 0
    for row in rows:
        text = str(row.get("text") or "")
        if text.strip():
            non_empty += 1
        if "memory" in text.lower() or "recall" in text.lower():
            referenced += 1
    if non_empty == 0:
        return 0.0
    return clamp01((referenced / non_empty) * 1.8)


def _goal_conflict() -> float:
    if not OPEN_QUESTIONS_PATH.exists():
        return 0.0
    lines = OPEN_QUESTIONS_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-500:]
    if not lines:
        return 0.0
    conflict_hits = 0
    for raw in lines:
        low = raw.lower()
        if "conflict" in low or "tension" in low or "tradeoff" in low:
            conflict_hits += 1
    return clamp01(conflict_hits / 60.0)


def _research_depth() -> float:
    queue = load_json(RESEARCH_QUEUE_PATH, {})
    findings = load_json(RESEARCH_FINDINGS_PATH, {})
    queued = len(queue.get("topics", [])) if isinstance(queue, dict) else 0
    completed = len(queue.get("completed", [])) if isinstance(queue, dict) else 0
    finding_rows = len(findings.get("findings", [])) if isinstance(findings, dict) else 0
    raw = math.log1p(queued + completed + finding_rows)
    return clamp01(raw / 5.5)


class TactiStateIngestor:
    def __init__(
        self,
        *,
        rate_hz: float = 2.0,
        output_path: Path = TACTI_STATE_PATH,
        mirror_output_path: Path = TACTI_STATE_MIRROR_PATH,
    ):
        ensure_runtime_dirs()
        self.rate_hz = max(0.5, float(rate_hz))
        self.output_path = output_path
        self.mirror_output_path = mirror_output_path
        self.log = JsonlLogger(RUNTIME_LOGS / "tacti_state_ingest.log")

    def sample(self) -> dict[str, Any]:
        active_agents = _active_agents()
        payload = {
            "ts": utc_now_iso(),
            "arousal": round(_arousal_scalar(), 4),
            "active_agents": active_agents,
            "token_flux": round(_token_flux(), 4),
            "memory_recall_density": round(_memory_recall_density(), 4),
            "goal_conflict": round(_goal_conflict(), 4),
            "research_depth": round(_research_depth(), 4),
        }
        return payload

    def emit_once(self) -> dict[str, Any]:
        payload = self.sample()
        atomic_write_json(self.output_path, payload)
        atomic_write_json(self.mirror_output_path, payload)
        return payload

    def run_forever(self, stop_event: Event | None = None) -> None:
        period = 1.0 / self.rate_hz
        self.log.log("tacti_ingest_start", rate_hz=self.rate_hz)
        next_log = time.monotonic()
        while True:
            if stop_event is not None and stop_event.is_set():
                self.log.log("tacti_ingest_stop")
                return
            t0 = time.monotonic()
            try:
                payload = self.emit_once()
                now = time.monotonic()
                if now >= next_log:
                    self.log.log(
                        "tacti_sample",
                        arousal=payload.get("arousal"),
                        token_flux=payload.get("token_flux"),
                        research_depth=payload.get("research_depth"),
                    )
                    next_log = now + 5.0
            except Exception as exc:
                self.log.log("tacti_ingest_error", error=str(exc))
            elapsed = time.monotonic() - t0
            sleep_for = period - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TACTI state ingestion")
    parser.add_argument("--rate-hz", type=float, default=2.0)
    parser.add_argument("--once", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    ingestor = TactiStateIngestor(rate_hz=args.rate_hz)
    if args.once:
        payload = ingestor.emit_once()
        print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
        return 0
    ingestor.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
