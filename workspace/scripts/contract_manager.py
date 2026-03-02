#!/usr/bin/env python3
"""
Dynamic Contract Manager (SERVICE vs CODE)

State:
- workspace/state_runtime/contract/current.json
- workspace/state_runtime/contract/events.jsonl (append-only)

Signals (local-only, optional):
- workspace/state_runtime/contract/signals/activity.jsonl
  Each line: {"ts": "...Z", "kind": "service_request"|"tool_call"|"manual_ping", "meta": {...}}
"""

from __future__ import annotations

import datetime
import json
import os
from typing import Any, Dict, List, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_STATE_DIR = os.path.join(ROOT, "workspace", "state_runtime", "contract")
STATE_DIR = os.path.abspath(os.environ.get("OPENCLAW_CONTRACT_STATE_DIR", DEFAULT_STATE_DIR))
CURRENT = os.path.join(STATE_DIR, "current.json")
EVENTS = os.path.join(STATE_DIR, "events.jsonl")
SIGNALS = os.path.join(STATE_DIR, "signals", "activity.jsonl")
QUEUE_PATH = os.path.abspath(
    os.environ.get("OPENCLAW_HEAVY_QUEUE_PATH") or os.path.join(ROOT, "workspace", "state_runtime", "queue", "heavy_jobs.jsonl")
)
RUNS_LOG = os.path.abspath(
    os.environ.get("OPENCLAW_HEAVY_RUNS_LOG") or os.path.join(ROOT, "workspace", "state_runtime", "queue", "heavy_runs.jsonl")
)


def now_utc_dt() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def utc_now() -> str:
    return now_utc_dt().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso_z(value: str) -> Optional[datetime.datetime]:
    try:
        s = str(value or "")
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        parsed = datetime.datetime.fromisoformat(s)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=datetime.UTC)
        return parsed.astimezone(datetime.UTC)
    except Exception:
        return None


def load_json(path: str, default: Any) -> Any:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
    except Exception:
        return default
    return default


def save_json(path: str, payload: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def append_event(event: Dict[str, Any]) -> None:
    ensure_state_dir()
    with open(EVENTS, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")


def ensure_state_dir() -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    os.makedirs(os.path.join(STATE_DIR, "signals"), exist_ok=True)


def read_recent_signals(minutes: int) -> List[Dict[str, Any]]:
    if not os.path.exists(SIGNALS):
        return []

    cutoff = now_utc_dt() - datetime.timedelta(minutes=minutes)
    out: List[Dict[str, Any]] = []
    try:
        with open(SIGNALS, "r", encoding="utf-8") as fh:
            for line in fh:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    ev = json.loads(raw)
                except Exception:
                    continue
                ts = parse_iso_z(str(ev.get("ts", "")))
                if ts and ts >= cutoff:
                    out.append(ev)
    except Exception:
        return []
    return out


def read_jsonl(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    out: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except Exception:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except Exception:
        return []
    return out


def queue_depth(queue_path: str = QUEUE_PATH, runs_log: str = RUNS_LOG) -> int:
    done_ids = set()
    for row in read_jsonl(runs_log):
        job_id = str(row.get("job_id", "")).strip()
        if not job_id:
            continue
        status = str(row.get("status", "")).strip()
        if status in {"ok", "failed", "expired", "invalid", "ensure_failed"}:
            done_ids.add(job_id)

    now = now_utc_dt()
    count = 0
    for row in read_jsonl(queue_path):
        if str(row.get("state", "")).strip() != "queued":
            continue
        job_id = str(row.get("id", "")).strip()
        if not job_id or job_id in done_ids:
            continue
        expiry = parse_iso_z(str(row.get("expires_at", "")))
        if expiry and expiry <= now:
            continue
        count += 1
    return count


def ewma(prev: Optional[float], value: float, alpha: float) -> float:
    if prev is None:
        return value
    return alpha * value + (1.0 - alpha) * prev


def default_policy() -> Dict[str, Any]:
    return {
        "window_minutes": 30,
        "alpha": 0.25,
        "service_rate_high": 0.30,
        "service_rate_low": 0.08,
        "min_mode_minutes": 20,
        "interrupt_rate": 0.20,
        "idle_window_seconds": 480,
    }


def compute_load(policy: Dict[str, Any]) -> Dict[str, Any]:
    minutes = int(policy["window_minutes"])
    idle_window_seconds = int(policy.get("idle_window_seconds", 480))
    signals = read_recent_signals(minutes)
    rate = len(signals) / max(minutes, 1)

    idle = True
    if signals:
        ts_values = [parse_iso_z(str(ev.get("ts", ""))) for ev in signals]
        ts_values = [x for x in ts_values if x is not None]
        if ts_values:
            last_ts = max(ts_values)
            idle = (now_utc_dt() - last_ts) > datetime.timedelta(seconds=idle_window_seconds)

    return {
        "events": len(signals),
        "window_minutes": minutes,
        "idle_window_seconds": idle_window_seconds,
        "rate_per_min": rate,
        "idle": idle,
    }


def init_current() -> Dict[str, Any]:
    now = utc_now()
    pol = default_policy()
    return {
        "ts": now,
        "mode": "SERVICE",
        "source": "FALLBACK",
        "override": None,
        "policy": pol,
        "service_load": {
            "events": 0,
            "window_minutes": pol["window_minutes"],
            "rate_per_min": 0.0,
            "idle": True,
            "ewma_rate": 0.0,
        },
        "last_transition": {
            "ts": now,
            "from": None,
            "to": "SERVICE",
            "reason": "init",
        },
        "interrupts": {
            "count": 0,
            "last_ts": None,
        },
        "queue_depth": 0,
    }


def override_is_active(override: Any) -> bool:
    if not isinstance(override, dict):
        return False
    ttl_raw = override.get("ttl_until")
    if ttl_raw is None:
        return True
    ttl_dt = parse_iso_z(str(ttl_raw))
    if not ttl_dt:
        return False
    return now_utc_dt() < ttl_dt


def should_transition(
    cur: Dict[str, Any],
    policy: Dict[str, Any],
    load: Dict[str, Any],
    *,
    queue_depth_now: int,
    service_override_active: bool,
) -> Optional[Dict[str, str]]:
    now = now_utc_dt()
    last_ts = parse_iso_z(str(cur.get("last_transition", {}).get("ts", ""))) or now
    if now - last_ts < datetime.timedelta(minutes=int(policy["min_mode_minutes"])):
        return None

    ewma_rate = float(cur.get("service_load", {}).get("ewma_rate", load["rate_per_min"]))
    hi = float(policy["service_rate_high"])
    lo = float(policy["service_rate_low"])

    if cur.get("mode") == "SERVICE":
        if ewma_rate <= lo and bool(load.get("idle")):
            if service_override_active:
                return None
            if queue_depth_now > 0:
                return {
                    "to": "CODE",
                    "reason": f"dynamic_backlog: low_rate={ewma_rate:.3f} idle={load['idle']} queue_depth={queue_depth_now}",
                }
            return {
                "to": "CODE",
                "reason": f"dynamic: low_rate={ewma_rate:.3f} idle={load['idle']}",
            }
    else:
        if ewma_rate >= hi:
            return {
                "to": "SERVICE",
                "reason": f"dynamic: high_rate={ewma_rate:.3f}",
            }
    return None


def apply_tick() -> Dict[str, Any]:
    ensure_state_dir()
    cur = load_json(CURRENT, None) or init_current()
    policy = cur.get("policy") or default_policy()

    now = utc_now()
    load = compute_load(policy)
    q_depth = queue_depth()
    prev = cur.get("service_load", {}).get("ewma_rate")
    prev_float = float(prev) if isinstance(prev, (int, float)) else None
    ewma_rate = ewma(prev_float, float(load["rate_per_min"]), float(policy["alpha"]))
    cur["service_load"] = {**load, "ewma_rate": ewma_rate}
    cur["queue_depth"] = q_depth
    cur["ts"] = now

    override = cur.get("override")
    if override:
        if override_is_active(override):
            if override.get("mode") == "CODE" and ewma_rate >= float(policy["interrupt_rate"]):
                interrupts = cur.setdefault("interrupts", {})
                interrupts["count"] = int(interrupts.get("count", 0)) + 1
                interrupts["last_ts"] = now
                append_event(
                    {
                        "ts": now,
                        "type": "interrupt_detected",
                        "mode": "CODE",
                        "rate": ewma_rate,
                        "reason": "load_above_interrupt_rate",
                        "override": override,
                    }
                )
            cur["mode"] = override.get("mode", cur.get("mode", "SERVICE"))
            cur["source"] = "MANUAL"
            save_json(CURRENT, cur)
            return cur

        append_event({"ts": now, "type": "override_expired", "override": override})
        cur["override"] = None

    if cur.get("source") == "MANUAL":
        # Manual override is no longer active; restore dynamic source labeling.
        cur["source"] = "DYNAMIC"

    service_override_active = override_is_active(cur.get("override")) and str((cur.get("override") or {}).get("mode", "")).upper() == "SERVICE"
    transition = should_transition(
        cur,
        policy,
        load,
        queue_depth_now=q_depth,
        service_override_active=service_override_active,
    )
    if transition:
        old_mode = cur.get("mode")
        cur["mode"] = transition["to"]
        cur["source"] = "DYNAMIC"
        cur["last_transition"] = {
            "ts": now,
            "from": old_mode,
            "to": transition["to"],
            "reason": transition["reason"],
        }
        append_event(
            {
                "ts": now,
                "type": "mode_transition",
                "from": old_mode,
                "to": transition["to"],
                "reason": transition["reason"],
                "rate": ewma_rate,
                "idle": load["idle"],
                "queue_depth": q_depth,
            }
        )

    save_json(CURRENT, cur)
    return cur


if __name__ == "__main__":
    state = apply_tick()
    print(
        json.dumps(
            {
                "ts": state["ts"],
                "mode": state["mode"],
                "source": state["source"],
                "ewma_rate": state["service_load"]["ewma_rate"],
                "idle": state["service_load"]["idle"],
                "queue_depth": state.get("queue_depth", 0),
            },
            sort_keys=True,
        )
    )
