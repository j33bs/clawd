"""TACTI(C)-R dashboard API helpers for Source UI."""

from __future__ import annotations

import importlib
import json
import os
import re
import resource
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = REPO_ROOT / "workspace"
REPORTS_ROOT = REPO_ROOT / "reports"


class ModuleUnavailableError(RuntimeError):
    """Raised when a runtime module cannot be imported."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def response_ok(data: dict[str, Any] | list[Any] | None) -> dict[str, Any]:
    return {
        "ok": True,
        "ts": now_iso(),
        "data": data,
        "error": None,
    }


def response_error(
    code: str,
    message: str,
    *,
    detail: Any | None = None,
    data: dict[str, Any] | list[Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "ts": now_iso(),
        "data": data,
        "error": {
            "code": str(code),
            "message": str(message),
        },
    }
    if detail is not None:
        payload["error"]["detail"] = detail
    return payload


def _ensure_runtime_paths() -> None:
    candidates = [
        WORKSPACE_ROOT,
        WORKSPACE_ROOT / "hivemind",
    ]
    for candidate in candidates:
        text = str(candidate)
        if text not in sys.path:
            sys.path.insert(0, text)


def _import_symbol(module_path: str, symbol: str | None = None):
    _ensure_runtime_paths()
    try:
        module = importlib.import_module(module_path)
    except Exception as exc:  # pragma: no cover - defensive runtime handling
        raise ModuleUnavailableError(f"{module_path}: {exc}") from exc
    if symbol is None:
        return module
    try:
        return getattr(module, symbol)
    except AttributeError as exc:
        raise ModuleUnavailableError(f"{module_path}.{symbol}: missing") from exc


def _read_json(path: Path) -> Any | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_jsonl(path: Path, limit: int = 20) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[-max(1, int(limit)) :]:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _qmd_probe(host: str = "127.0.0.1", port: int = 8181, timeout_s: float = 0.35) -> dict[str, Any]:
    started = time.perf_counter()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout_s)
    try:
        result = sock.connect_ex((host, port))
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        if result == 0:
            return {
                "reachable": True,
                "latency_ms": latency_ms,
                "target": f"{host}:{port}",
            }
        return {
            "reachable": False,
            "latency_ms": latency_ms,
            "target": f"{host}:{port}",
            "reason": f"connect_ex={result}",
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        return {
            "reachable": False,
            "latency_ms": latency_ms,
            "target": f"{host}:{port}",
            "reason": str(exc),
        }
    finally:
        try:
            sock.close()
        except Exception:
            pass


def _parse_iso(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _knowledge_sync_status() -> dict[str, Any]:
    marker = WORKSPACE_ROOT / "knowledge_base" / "data" / "last_sync.txt"
    if not marker.exists():
        return {
            "status": "unknown",
            "reason": f"missing marker: {marker}",
        }
    text = marker.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
    stamp = text[0].strip() if text else ""
    parsed = _parse_iso(stamp)
    if parsed is None:
        return {
            "status": "unknown",
            "reason": "marker exists but timestamp parse failed",
            "last_sync": stamp or None,
        }
    age_seconds = max(0.0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds())
    age_minutes = round(age_seconds / 60.0, 2)
    freshness = "ok" if age_seconds <= 86400 else "stale"
    return {
        "status": freshness,
        "last_sync": parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "age_minutes": age_minutes,
    }


def _cron_status() -> dict[str, Any]:
    template_path = WORKSPACE_ROOT / "automation" / "cron_jobs.json"
    template_jobs = 0
    template_error = None
    if template_path.exists():
        payload = _read_json(template_path)
        if isinstance(payload, dict) and isinstance(payload.get("jobs"), list):
            template_jobs = len(payload["jobs"])
        elif isinstance(payload, list):
            template_jobs = len(payload)
        else:
            template_error = "template parse failed"
    else:
        template_error = f"missing template: {template_path}"

    status_dir = REPORTS_ROOT / "automation" / "job_status"
    latest_file = None
    latest_ts = None
    if status_dir.exists() and status_dir.is_dir():
        for candidate in status_dir.glob("*.json"):
            try:
                mtime = candidate.stat().st_mtime
            except Exception:
                continue
            if latest_ts is None or mtime > latest_ts:
                latest_ts = mtime
                latest_file = candidate

    heartbeat_state = REPO_ROOT / "memory" / "heartbeat-state.json"
    heartbeat_seen = heartbeat_state.exists()

    if latest_ts is None:
        detail: dict[str, Any] = {
            "status": "unknown",
            "template_jobs": template_jobs,
            "heartbeat_state_seen": heartbeat_seen,
            "reason": f"no artifacts in {status_dir}",
        }
        if template_error:
            detail["template_error"] = template_error
        return detail

    latest_dt = datetime.fromtimestamp(latest_ts, tz=timezone.utc)
    age_seconds = max(0.0, (datetime.now(timezone.utc) - latest_dt).total_seconds())
    freshness = "ok" if age_seconds <= 86400 else "stale"
    result = {
        "status": freshness,
        "template_jobs": template_jobs,
        "latest_artifact": str(latest_file),
        "latest_artifact_ts": latest_dt.isoformat().replace("+00:00", "Z"),
        "age_minutes": round(age_seconds / 60.0, 2),
        "heartbeat_state_seen": heartbeat_seen,
    }
    if template_error:
        result["template_error"] = template_error
    return result


def _system_memory_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    try:
        max_rss = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        # Linux reports KiB, macOS reports bytes.
        process_mb = max_rss / (1024.0 * 1024.0) if max_rss > 10_000_000 else max_rss / 1024.0
        snapshot["process_rss_mb"] = round(process_mb, 2)
    except Exception as exc:
        snapshot["process_rss_error"] = str(exc)

    try:
        page_size = float(os.sysconf("SC_PAGE_SIZE"))
        total_pages = float(os.sysconf("SC_PHYS_PAGES"))
        available_pages = float(os.sysconf("SC_AVPHYS_PAGES"))
        total_mb = (page_size * total_pages) / (1024.0 * 1024.0)
        available_mb = (page_size * available_pages) / (1024.0 * 1024.0)
        used_mb = max(0.0, total_mb - available_mb)
        snapshot.update(
            {
                "system_total_mb": round(total_mb, 2),
                "system_available_mb": round(available_mb, 2),
                "system_used_mb": round(used_mb, 2),
                "system_used_pct": round(_safe_ratio(used_mb, total_mb) * 100.0, 2),
            }
        )
    except Exception as exc:
        snapshot["system_memory_error"] = str(exc)

    return snapshot


def get_status_data() -> dict[str, Any]:
    return {
        "qmd": _qmd_probe(),
        "knowledge_base_sync": _knowledge_sync_status(),
        "cron": _cron_status(),
        "memory": _system_memory_snapshot(),
    }


def get_dream_status(limit: int = 20) -> dict[str, Any]:
    _import_symbol("tacti_cr.dream_consolidation", "run_consolidation")

    store_path = WORKSPACE_ROOT / "hivemind" / "data" / "dream_store.jsonl"
    report_dir = WORKSPACE_ROOT / "memory" / "dream_reports"

    store_items = len(_read_jsonl(store_path, limit=100000)) if store_path.exists() else 0

    reports = sorted(report_dir.glob("*.md"), key=lambda p: p.stat().st_mtime if p.exists() else 0.0)
    latest_report = reports[-1] if reports else None
    last_summary = None
    last_run_ts = None
    if latest_report is not None:
        last_run_ts = datetime.fromtimestamp(latest_report.stat().st_mtime, tz=timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )
        lines = latest_report.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("-"):
                last_summary = stripped.lstrip("- ").strip()
                break

    return {
        "status": "ready" if latest_report else "idle",
        "store_items": store_items,
        "report_count": len(reports),
        "last_run": last_run_ts,
        "last_outcome_summary": last_summary,
        "latest_report": str(latest_report) if latest_report else None,
        "list_limit": max(1, int(limit)),
    }


def run_dream_consolidation(day: str | None = None) -> dict[str, Any]:
    run_consolidation = _import_symbol("tacti_cr.dream_consolidation", "run_consolidation")
    target_day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result = run_consolidation(REPO_ROOT, day=target_day)
    if not isinstance(result, dict):
        return {
            "result": str(result),
            "day": target_day,
        }
    return result


def get_stigmergy_status(limit: int = 20) -> dict[str, Any]:
    StigmergyMap = _import_symbol("hivemind.stigmergy", "StigmergyMap")
    marks = StigmergyMap().query_marks(top_n=max(1, int(limit)))
    intensities = [float(x.get("effective_intensity", 0.0)) for x in marks]
    active = [x for x in marks if float(x.get("effective_intensity", 0.0)) > 0.0]

    if intensities:
        summary = {
            "min": round(min(intensities), 6),
            "avg": round(sum(intensities) / len(intensities), 6),
            "max": round(max(intensities), 6),
        }
    else:
        summary = {"min": 0.0, "avg": 0.0, "max": 0.0}

    trimmed = [
        {
            "topic": str(row.get("topic", "")),
            "effective_intensity": float(row.get("effective_intensity", 0.0)),
            "deposited_by": str(row.get("deposited_by", "")),
            "timestamp": str(row.get("timestamp", "")),
        }
        for row in marks[: max(1, int(limit))]
    ]

    return {
        "active_marks_count": len(active),
        "intensity_summary": summary,
        "marks": trimmed,
    }


def query_stigmergy(text: str, limit: int = 20) -> dict[str, Any]:
    query = str(text or "").strip().lower()
    if not query:
        return {
            "query": "",
            "matches": [],
            "count": 0,
        }

    payload = get_stigmergy_status(limit=max(1, int(limit) * 3))
    marks = payload.get("marks", []) if isinstance(payload, dict) else []
    matches = []
    for row in marks:
        topic = str(row.get("topic", "")).lower()
        deposited_by = str(row.get("deposited_by", "")).lower()
        if query in topic or query in deposited_by:
            matches.append(row)
    return {
        "query": query,
        "count": len(matches),
        "matches": matches[: max(1, int(limit))],
    }


def get_immune_status(limit: int = 20) -> dict[str, Any]:
    _import_symbol("tacti_cr.semantic_immune", "assess_content")

    state_dir = WORKSPACE_ROOT / "state" / "semantic_immune"
    stats_path = state_dir / "stats.json"
    quarantine_path = state_dir / "quarantine.jsonl"
    approvals_path = state_dir / "approvals.jsonl"

    stats = _read_json(stats_path)
    stats = stats if isinstance(stats, dict) else {}

    quarantine_rows = _read_jsonl(quarantine_path, limit=max(1000, int(limit) * 10))
    approvals_rows = _read_jsonl(approvals_path, limit=2000)
    recent = quarantine_rows[-max(1, int(limit)) :]

    recent_blocks = [
        {
            "ts": str(row.get("ts", "")),
            "content_hash": str(row.get("content_hash", "")),
            "score": float(row.get("score", 0.0)),
            "threshold": float(row.get("threshold", 0.0)),
            "reason": str(row.get("reason", "")),
        }
        for row in recent
    ]

    return {
        "quarantine_count": len(quarantine_rows),
        "approval_count": len(approvals_rows),
        "accepted_count": int(stats.get("count", 0)),
        "recent_blocks": recent_blocks,
    }


def get_arousal_status() -> dict[str, Any]:
    ArousalOscillator = _import_symbol("tacti_cr.arousal_oscillator", "ArousalOscillator")
    oscillator = ArousalOscillator(repo_root=REPO_ROOT)
    explain = oscillator.explain()

    bins, bins_used = oscillator._learned_bins()  # noqa: SLF001 - read-only dashboard summary
    histogram = [
        {
            "hour": int(hour),
            "value": round(float(value), 6),
        }
        for hour, value in enumerate(bins[:24])
    ]

    return {
        "current_energy": float(explain.get("multiplier", 0.0)),
        "baseline": float(explain.get("baseline", 0.0)),
        "learned": float(explain.get("learned", 0.0)),
        "bins_used": int(bins_used),
        "hourly_histogram": histogram,
    }


def _tag_summary(rows: list[dict[str, Any]], top_n: int = 10) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for row in rows:
        tags = row.get("tags", [])
        if not isinstance(tags, list):
            continue
        for raw_tag in tags:
            tag = str(raw_tag).strip()
            if not tag:
                continue
            counts[tag] = counts.get(tag, 0) + 1
    out = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"tag": tag, "count": count} for tag, count in out[: max(1, int(top_n))]]


def get_trails_status(limit: int = 20) -> dict[str, Any]:
    TrailStore = _import_symbol("hivemind.trails", "TrailStore")

    store = TrailStore()
    snapshot = store.snapshot()
    trails_path = Path(str(snapshot.get("path", "")))
    rows = _read_jsonl(trails_path, limit=max(200, int(limit) * 5))
    recent = rows[-max(1, int(limit)) :]

    strengths = [float(row.get("strength", 0.0)) for row in rows] if rows else []
    if strengths:
        strength_summary = {
            "min": round(min(strengths), 6),
            "avg": round(sum(strengths) / len(strengths), 6),
            "max": round(max(strengths), 6),
        }
    else:
        strength_summary = {"min": 0.0, "avg": 0.0, "max": 0.0}

    recent_payload = []
    for row in reversed(recent):
        text = str(row.get("text", ""))
        recent_payload.append(
            {
                "trail_id": str(row.get("trail_id", "")),
                "text": text[:180],
                "tags": [str(x) for x in row.get("tags", []) if str(x)][:8],
                "strength": float(row.get("strength", 0.0)),
                "updated_at": str(row.get("updated_at") or row.get("created_at") or ""),
            }
        )

    return {
        "memory_heatmap_summary": {
            "trail_count": int(snapshot.get("count", 0)),
            "strength_summary": strength_summary,
            "top_tags": _tag_summary(rows, top_n=10),
        },
        "recent_trails": recent_payload,
    }


def trigger_trail(text: str | None, tags: list[str] | None = None, strength: float | None = None) -> dict[str, Any]:
    TrailStore = _import_symbol("hivemind.trails", "TrailStore")
    store = TrailStore()

    clean_text = str(text or "").strip()
    if not clean_text:
        clean_text = "manual trail trigger"
    clean_text = clean_text[:200]

    normalized_tags: list[str] = []
    for tag in tags or []:
        raw = str(tag).strip().lower()
        if not raw:
            continue
        if not re.fullmatch(r"[a-z0-9_\-]{1,32}", raw):
            continue
        normalized_tags.append(raw)
        if len(normalized_tags) >= 6:
            break

    payload = {
        "text": clean_text,
        "tags": normalized_tags,
    }
    if strength is not None:
        payload["strength"] = max(0.05, min(5.0, float(strength)))

    trail_id = store.add(payload)
    return {
        "trail_id": trail_id,
        "text": clean_text,
        "tags": normalized_tags,
    }


def get_peer_graph_status(limit: int = 20) -> dict[str, Any]:
    _import_symbol("hivemind.peer_graph", "PeerGraph")

    candidate_paths = [
        WORKSPACE_ROOT / "artifacts" / "tacti_system" / "verify_report.json",
    ]
    payload = None
    source_path = None
    for path in candidate_paths:
        raw = _read_json(path)
        if not isinstance(raw, dict):
            continue
        snapshot = raw.get("snapshot") if isinstance(raw.get("snapshot"), dict) else raw
        peer_graph = snapshot.get("peer_graph") if isinstance(snapshot, dict) else None
        if isinstance(peer_graph, dict):
            payload = peer_graph
            source_path = path
            break

    if not isinstance(payload, dict):
        raise RuntimeError("No peer graph snapshot artifact found")

    agents = payload.get("agents", []) if isinstance(payload.get("agents"), list) else []
    edges_obj = payload.get("edges", {}) if isinstance(payload.get("edges"), dict) else {}
    edge_count = 0
    sample = []
    for src, row in edges_obj.items():
        if not isinstance(row, dict):
            continue
        for dst, state in row.items():
            if not isinstance(state, dict):
                continue
            edge_count += 1
            if len(sample) < max(1, int(limit)):
                sample.append(
                    {
                        "src": str(src),
                        "dst": str(dst),
                        "weight": float(state.get("weight", 0.0)),
                    }
                )

    return {
        "nodes_count": len(agents),
        "edges_count": edge_count,
        "agents": [str(x) for x in agents[: max(1, int(limit))]],
        "adjacency_sample": sample,
        "source": str(source_path) if source_path else None,
    }


def get_skills(limit: int = 100) -> dict[str, Any]:
    root = WORKSPACE_ROOT / "skill-graph"
    skills_dir = root / "skills"
    mocs_dir = root / "mocs"
    index_file = root / "index.md"

    if not root.exists():
        return {
            "skills": [],
            "links": [],
            "reason": f"missing directory: {root}",
        }

    skills = []
    if skills_dir.exists():
        for path in sorted(skills_dir.glob("*.md"))[: max(1, int(limit))]:
            skills.append(
                {
                    "name": path.stem,
                    "path": str(path),
                    "href": f"/workspace/skill-graph/skills/{path.name}",
                }
            )

    mocs = []
    if mocs_dir.exists():
        for path in sorted(mocs_dir.glob("*.md"))[: max(1, int(limit))]:
            mocs.append(
                {
                    "name": path.stem,
                    "path": str(path),
                    "href": f"/workspace/skill-graph/mocs/{path.name}",
                }
            )

    links = []
    if index_file.exists():
        links.append({"name": "index", "path": str(index_file), "href": "/workspace/skill-graph/index.md"})
    graph_py = root / "skill_graph.py"
    if graph_py.exists():
        links.append({"name": "skill_graph.py", "path": str(graph_py), "href": "/workspace/skill-graph/skill_graph.py"})

    return {
        "skills": skills,
        "mocs": mocs,
        "links": links,
        "count": len(skills),
    }


__all__ = [
    "ModuleUnavailableError",
    "get_arousal_status",
    "get_dream_status",
    "get_immune_status",
    "get_peer_graph_status",
    "get_skills",
    "get_status_data",
    "get_stigmergy_status",
    "get_trails_status",
    "query_stigmergy",
    "response_error",
    "response_ok",
    "run_dream_consolidation",
    "trigger_trail",
]
