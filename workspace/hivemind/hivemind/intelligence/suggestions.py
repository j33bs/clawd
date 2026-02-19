from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from ..store import HiveMindStore

REPO_ROOT = Path(__file__).resolve().parents[4]
STATE_PATH = REPO_ROOT / "workspace" / "hivemind" / "suggestions_state.json"
MAX_PER_SESSION = 3
COOLDOWN = timedelta(hours=1)


def _iso(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _load_state(path: Path = STATE_PATH) -> Dict[str, Any]:
    if not path.exists():
        return {"sessions": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"sessions": {}}


def _save_state(state: Dict[str, Any], path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _can_view(agent: str, item_scope: str) -> bool:
    return item_scope == "shared" or item_scope == agent


def generate_suggestions(context: str, agent: str, session_id: str = "default") -> List[Dict[str, Any]]:
    store = HiveMindStore()
    now = datetime.now(timezone.utc)
    state = _load_state()
    s = state.setdefault("sessions", {}).setdefault(session_id, {}).setdefault(agent, {"count": 0, "last": None})

    last = s.get("last")
    if isinstance(last, str):
        try:
            if now - _iso(last) < COOLDOWN:
                return []
        except Exception:
            pass
    if int(s.get("count", 0)) >= MAX_PER_SESSION:
        return []

    units = [u for u in store.all_units() if _can_view(agent, str(u.get("agent_scope", "shared")))]
    suggestions: List[Dict[str, Any]] = []

    # 1) Temporal patterns from query logs
    q_events = [e for e in store.read_log() if e.get("event") == "query" and e.get("agent") == agent]
    if len(q_events) >= 3:
        topic = str(context or "").strip()
        recent = [e for e in q_events if topic.lower() in str(e.get("query", "")).lower()]
        if len(recent) >= 3:
            suggestions.append(
                {
                    "type": "temporal",
                    "message": f"You query '{topic}' repeatedly; consider reusing prior fix context.",
                    "related_ku_ids": [],
                    "action_hint": f"query --q '{topic}'",
                }
            )

    # 2) Unfinished threads older than 48h
    cutoff_unfinished = now - timedelta(hours=48)
    for u in units:
        if u.get("kind") != "handoff":
            continue
        status = str((u.get("metadata") or {}).get("status", "")).lower()
        if status not in {"in_progress", "open", "pending"}:
            continue
        try:
            created = _iso(str(u.get("created_at")))
        except Exception:
            continue
        if created <= cutoff_unfinished:
            suggestions.append(
                {
                    "type": "unfinished",
                    "message": "You have an in-progress handoff older than 48h.",
                    "related_ku_ids": [f"ku_{str(u.get('content_hash', ''))[:12]}"],
                    "action_hint": "query --q 'handoff status'",
                }
            )
            break

    # 3) Related queries by context keywords
    if context:
        related = store.search(agent_scope=agent, query=context, limit=1)
        if related:
            top = related[0]
            suggestions.append(
                {
                    "type": "related",
                    "message": f"Related memory found for '{context}'.",
                    "related_ku_ids": [f"ku_{str(top.get('content_hash', ''))[:12]}"],
                    "action_hint": f"query --q '{context}'",
                }
            )

    # 4) Stale knowledge hint
    stale_cutoff = now - timedelta(days=90)
    for u in units:
        ts = str(u.get("last_accessed_at") or u.get("created_at") or "")
        if not ts:
            continue
        try:
            ref = _iso(ts)
        except Exception:
            continue
        if ref < stale_cutoff and u.get("kind") not in {"decision", "architecture"}:
            suggestions.append(
                {
                    "type": "stale",
                    "message": "Some knowledge appears stale; consider archive review.",
                    "related_ku_ids": [f"ku_{str(u.get('content_hash', ''))[:12]}"],
                    "action_hint": "prune --dry-run",
                }
            )
            break

    out = suggestions[:MAX_PER_SESSION]
    if out:
        s["count"] = int(s.get("count", 0)) + len(out)
        s["last"] = now.isoformat()
        _save_state(state)
    return out
