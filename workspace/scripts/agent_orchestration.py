#!/usr/bin/env python3
"""Reusable sub-agent orchestration primitives for sessions_spawn workflows."""

from __future__ import annotations

import heapq
import json
import os
import resource
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_MAX_CONCURRENT = 4
MIN_TIMEOUT_SECONDS = 15
MAX_TIMEOUT_SECONDS = 900

PRIORITY_RANK = {
    "high": 0,
    "normal": 1,
    "low": 2,
}

SPECIALIZATION_KEYWORDS = {
    "coding": ("code", "bug", "test", "refactor", "build", "script", "debug"),
    "research": ("research", "analyze", "investigate", "paper", "evidence", "audit"),
    "conversation": ("chat", "reply", "talk", "message", "conversation"),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_positive_int(value: str | None, default: int) -> int:
    if value is None or not str(value).strip():
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def clamp_timeout(value: int) -> int:
    return max(MIN_TIMEOUT_SECONDS, min(MAX_TIMEOUT_SECONDS, value))


def resolve_specialization_tags(task: str, explicit_tags: list[str] | None = None) -> list[str]:
    tags: list[str] = []
    if explicit_tags:
        tags.extend(tag.strip().lower() for tag in explicit_tags if str(tag).strip())
    lowered = task.lower()
    for tag, keywords in SPECIALIZATION_KEYWORDS.items():
        if any(word in lowered for word in keywords):
            tags.append(tag)
    if not tags:
        tags.append("conversation")
    deduped = []
    seen = set()
    for tag in tags:
        if tag in seen:
            continue
        seen.add(tag)
        deduped.append(tag)
    return deduped


def _load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return raw if isinstance(raw, dict) else default


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


@dataclass
class SpawnQueueEntry:
    priority_rank: int
    seq: int
    request: dict

    def to_heap_item(self):
        return (self.priority_rank, self.seq, self.request)


class AgentOrchestrator:
    def __init__(
        self,
        state_dir: Path,
        *,
        timeout_default: int = DEFAULT_TIMEOUT_SECONDS,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
    ):
        self.state_dir = Path(state_dir)
        self.state_path = self.state_dir / "state.json"
        self.handoff_log_path = self.state_dir / "handoffs.jsonl"
        self.resource_log_path = self.state_dir / "resource_usage.jsonl"
        self.timeout_default = clamp_timeout(timeout_default)
        self.max_concurrent = max(1, max_concurrent)
        self._seq = 0
        self.state = self._load_state()
        self._queue: list[tuple[int, int, dict]] = []
        self._rehydrate_queue()

    def _load_state(self) -> dict:
        state = _load_json(
            self.state_path,
            {
                "schema": 1,
                "agents": {},
                "active_runs": {},
                "provider_load": {},
                "queue": [],
                "handoff_ack": {},
                "shutdown": None,
            },
        )
        for key in ("agents", "active_runs", "provider_load", "handoff_ack"):
            if not isinstance(state.get(key), dict):
                state[key] = {}
        if not isinstance(state.get("queue"), list):
            state["queue"] = []
        if "schema" not in state:
            state["schema"] = 1
        return state

    def _rehydrate_queue(self) -> None:
        queue_items = []
        seq = 0
        for raw in self.state.get("queue", []):
            if not isinstance(raw, dict):
                continue
            rank = int(raw.get("priority_rank", PRIORITY_RANK["normal"]))
            item_seq = int(raw.get("seq", seq))
            request = raw.get("request")
            if not isinstance(request, dict):
                continue
            queue_items.append((rank, item_seq, request))
            seq = max(seq, item_seq + 1)
        heapq.heapify(queue_items)
        self._queue = queue_items
        self._seq = seq

    def _persist(self) -> None:
        self.state["queue"] = [
            {"priority_rank": rank, "seq": seq, "request": request}
            for (rank, seq, request) in sorted(self._queue)
        ]
        _write_json(self.state_path, self.state)

    def resolve_timeout_seconds(self, timeout_seconds: int | None = None) -> int:
        if timeout_seconds is None:
            return self.timeout_default
        return clamp_timeout(int(timeout_seconds))

    def set_agent_state(self, agent_id: str, patch: dict[str, Any]) -> dict:
        entry = self.state["agents"].get(agent_id)
        if not isinstance(entry, dict):
            entry = {}
        entry.update(patch)
        entry["updated_at"] = utc_now()
        self.state["agents"][agent_id] = entry
        self._persist()
        return entry

    def get_agent_state(self, agent_id: str) -> dict:
        entry = self.state["agents"].get(agent_id)
        return entry if isinstance(entry, dict) else {}

    def enqueue_spawn_request(self, request: dict, *, priority: str = "normal") -> dict:
        rank = PRIORITY_RANK.get(priority, PRIORITY_RANK["normal"])
        entry = SpawnQueueEntry(priority_rank=rank, seq=self._seq, request=request)
        self._seq += 1
        heapq.heappush(self._queue, entry.to_heap_item())
        self._persist()
        return {
            "queued": True,
            "priority": priority if priority in PRIORITY_RANK else "normal",
            "queue_depth": len(self._queue),
        }

    def dequeue_spawn_request(self) -> dict | None:
        if not self._queue:
            return None
        _, _, request = heapq.heappop(self._queue)
        self._persist()
        return request

    def select_provider(self, providers: list[str]) -> str:
        if not providers:
            return "default"
        load = self.state.get("provider_load", {})
        return sorted(providers, key=lambda p: (int(load.get(p, 0)), p))[0]

    def prepare_spawn(
        self,
        task: str,
        *,
        context: dict | None = None,
        timeout_seconds: int | None = None,
        priority: str = "normal",
        specialization_tags: list[str] | None = None,
        providers: list[str] | None = None,
        enqueue_if_busy: bool = True,
    ) -> dict:
        providers = providers or ["default"]
        resolved_priority = priority if priority in PRIORITY_RANK else "normal"
        payload = {
            "task": task,
            "context": context or {},
            "timeout_seconds": self.resolve_timeout_seconds(timeout_seconds),
            "priority": resolved_priority,
            "specialization_tags": resolve_specialization_tags(task, specialization_tags),
            "provider": self.select_provider(providers),
        }
        if enqueue_if_busy and len(self.state.get("active_runs", {})) >= self.max_concurrent:
            queue_meta = self.enqueue_spawn_request(payload, priority=resolved_priority)
            return {**payload, **queue_meta}
        return {**payload, "queued": False, "queue_depth": len(self._queue)}

    def create_handoff(self, from_agent: str, to_agent: str, summary: str, payload: dict | None = None) -> str:
        handoff_id = f"handoff-{uuid.uuid4().hex[:12]}"
        record = {
            "handoff_id": handoff_id,
            "status": "pending",
            "from_agent": from_agent,
            "to_agent": to_agent,
            "summary": summary,
            "payload": payload or {},
            "created_at": utc_now(),
        }
        self.handoff_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.handoff_log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=True) + "\n")
        return handoff_id

    def acknowledge_handoff(self, handoff_id: str, acknowledged_by: str, note: str = "") -> dict:
        ack = {
            "status": "acknowledged",
            "acknowledged_by": acknowledged_by,
            "acknowledged_at": utc_now(),
            "note": note,
        }
        self.state["handoff_ack"][handoff_id] = ack
        self._persist()
        return ack

    def get_handoff_status(self, handoff_id: str) -> dict:
        ack = self.state.get("handoff_ack", {}).get(handoff_id)
        if isinstance(ack, dict):
            return ack
        return {"status": "pending"}

    def register_run_start(self, agent_id: str, provider: str, request: dict | None = None) -> str:
        run_id = f"run-{uuid.uuid4().hex[:12]}"
        usage = resource.getrusage(resource.RUSAGE_SELF)
        self.state["active_runs"][run_id] = {
            "agent_id": agent_id,
            "provider": provider,
            "started_at": utc_now(),
            "started_monotonic": time.monotonic(),
            "rss_start_kb": int(getattr(usage, "ru_maxrss", 0)),
            "request": request or {},
        }
        self.state["provider_load"][provider] = int(self.state["provider_load"].get(provider, 0)) + 1
        self._persist()
        return run_id

    def register_run_end(self, run_id: str, *, status: str = "ok", state_update: dict | None = None) -> dict:
        run = self.state["active_runs"].pop(run_id, None)
        if not isinstance(run, dict):
            return {"ended": False, "reason": "run_not_found"}

        provider = str(run.get("provider") or "default")
        self.state["provider_load"][provider] = max(0, int(self.state["provider_load"].get(provider, 1)) - 1)

        elapsed_ms = max(0, int((time.monotonic() - float(run.get("started_monotonic", time.monotonic()))) * 1000))
        rss_now = int(getattr(resource.getrusage(resource.RUSAGE_SELF), "ru_maxrss", 0))
        rss_delta = rss_now - int(run.get("rss_start_kb", rss_now))
        agent_id = str(run.get("agent_id") or "unknown")
        if state_update:
            self.set_agent_state(agent_id, state_update)

        self.resource_log_path.parent.mkdir(parents=True, exist_ok=True)
        metric = {
            "run_id": run_id,
            "agent_id": agent_id,
            "provider": provider,
            "status": status,
            "duration_ms": elapsed_ms,
            "rss_delta_kb": rss_delta,
            "ended_at": utc_now(),
        }
        with self.resource_log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(metric, ensure_ascii=True) + "\n")

        self._persist()
        return {"ended": True, **metric}

    def graceful_shutdown(self, reason: str = "manual") -> dict:
        self.state["shutdown"] = {
            "reason": reason,
            "at": utc_now(),
            "active_runs": len(self.state.get("active_runs", {})),
            "queued": len(self._queue),
        }
        self._persist()
        return self.state["shutdown"]


def build_default_orchestrator(repo_root: Path | None = None) -> AgentOrchestrator:
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[2]
    timeout_default = parse_positive_int(
        os.environ.get("OPENCLAW_SESSIONS_SPAWN_TIMEOUT_SECONDS"),
        DEFAULT_TIMEOUT_SECONDS,
    )
    max_concurrent = parse_positive_int(
        os.environ.get("OPENCLAW_SUBAGENT_MAX_CONCURRENT"),
        DEFAULT_MAX_CONCURRENT,
    )
    state_dir = Path(
        os.environ.get(
            "OPENCLAW_AGENT_ORCHESTRATION_STATE_DIR",
            str(repo_root / "workspace" / "state_runtime" / "agent_orchestration"),
        )
    )
    return AgentOrchestrator(
        state_dir=state_dir,
        timeout_default=timeout_default,
        max_concurrent=max_concurrent,
    )


__all__ = [
    "AgentOrchestrator",
    "build_default_orchestrator",
    "clamp_timeout",
    "resolve_specialization_tags",
]
