#!/usr/bin/env python3
"""Generate a bounded Grokness tuning report and optionally apply safe routing tweaks."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def _coerce_int(value, default):
    try:
        return int(value)
    except Exception:
        return default


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class EvolverResult:
    def __init__(self, report_path: Path, json_path: Path, applied: dict, suggestions: list[str]) -> None:
        self.report_path = report_path
        self.json_path = json_path
        self.applied = applied
        self.suggestions = suggestions


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _scan_router_events(path: Path) -> dict:
    stats = {
        "exists": path.exists(),
        "success_by_provider": {},
        "failure_by_provider": {},
        "context_too_large_local": 0,
        "escalations": 0,
    }
    if not path.exists():
        return stats
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            row = json.loads(raw)
        except Exception:
            continue
        event = row.get("event")
        detail = row.get("detail", {}) or {}
        provider = str(detail.get("provider") or detail.get("from_provider") or "")
        reason = str(detail.get("reason_code") or "")
        if event == "router_success" and provider:
            stats["success_by_provider"][provider] = stats["success_by_provider"].get(provider, 0) + 1
        elif event in {"router_attempt", "router_escalate"}:
            if provider:
                stats["failure_by_provider"][provider] = stats["failure_by_provider"].get(provider, 0) + 1
            if event == "router_escalate":
                stats["escalations"] += 1
        if reason in {"context_too_large_for_local", "context_too_large_after_compression"}:
            stats["context_too_large_local"] += 1
    return stats


def _render_report(policy: dict, event_stats: dict, suggestions: list[str], applied: dict, snapshot_path: Path) -> str:
    router = (((policy.get("routing") or {}).get("capability_router") or {}))
    lines = [
        "# Grok Evolver Report",
        "",
        f"- Generated: {_utc_now()}",
        f"- Token snapshot: `{snapshot_path}`",
        f"- Router events present: {event_stats['exists']}",
        "",
        "## Current Routing",
        f"- chatProvider: `{router.get('chatProvider', '') or '(unset)'}`",
        f"- planningProvider: `{router.get('planningProvider', '') or '(unset)'}`",
        f"- reasoningProvider: `{router.get('reasoningProvider', '') or '(unset)'}`",
        f"- codeProvider: `{router.get('codeProvider', '') or '(unset)'}`",
        f"- smallCodeProvider: `{router.get('smallCodeProvider', '') or '(unset)'}`",
        f"- localChatMaxChars: {router.get('localChatMaxChars', '(unset)')}",
        f"- reasoningEscalationTokens: {router.get('reasoningEscalationTokens', '(unset)')}",
        "",
        "## Event Signals",
        f"- local_context_overflows: {event_stats['context_too_large_local']}",
        f"- escalations: {event_stats['escalations']}",
        f"- local_successes: {sum(v for k, v in event_stats['success_by_provider'].items() if k.startswith('local_') or k == 'ollama')}",
        f"- grok_successes: {event_stats['success_by_provider'].get('grok_api', 0)}",
        "",
        "## Suggestions",
    ]
    if suggestions:
        for item in suggestions:
            lines.append(f"- {item}")
    else:
        lines.append("- No changes suggested.")
    lines.extend(["", "## Applied Safe Changes"])
    if applied:
        for key, value in applied.items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- None.")
    return "\n".join(lines) + "\n"


def run(repo_root: Path, apply_safe: bool) -> EvolverResult:
    policy_path = repo_root / "workspace" / "policy" / "llm_policy.json"
    events_path = repo_root / "itc" / "llm_router_events.jsonl"
    reports_dir = repo_root / "reports" / "grokness"
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    snapshot_path = reports_dir / f"token-burn-{stamp}.md"
    report_path = reports_dir / f"{stamp}.md"
    json_path = reports_dir / f"{stamp}.json"

    subprocess.run(
        [
            "python3",
            str(repo_root / "workspace" / "scripts" / "report_token_burn.py"),
            "--max-files",
            "8",
            "--out",
            str(snapshot_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    policy = _load_json(policy_path, {})
    router = (((policy.get("routing") or {}).get("capability_router") or {}))
    event_stats = _scan_router_events(events_path)
    suggestions = []
    applied = {}

    local_chat_max = _coerce_int(router.get("localChatMaxChars"), 320)
    new_local_chat_max = local_chat_max

    if event_stats["context_too_large_local"] >= 5 and local_chat_max > 240:
        new_local_chat_max = max(240, local_chat_max - 40)
        suggestions.append(
            f"Reduce localChatMaxChars from {local_chat_max} to {new_local_chat_max} because local overflows are recurring."
        )
    elif event_stats["success_by_provider"].get("grok_api", 0) >= 20 and event_stats["context_too_large_local"] == 0 and local_chat_max < 640:
        new_local_chat_max = min(640, local_chat_max + 40)
        suggestions.append(
            f"Increase localChatMaxChars from {local_chat_max} to {new_local_chat_max} to reclaim more cheap local chat traffic."
        )

    for key, value in {
        "chatProvider": "grok_api",
        "planningProvider": "grok_api",
        "reasoningProvider": "grok_api",
        "codeProvider": "grok_api",
        "smallCodeProvider": "local_vllm_assistant",
    }.items():
        if router.get(key) != value:
            suggestions.append(f"Set capability_router.{key} to `{value}`.")

    if apply_safe and new_local_chat_max != local_chat_max:
        router["localChatMaxChars"] = new_local_chat_max
        policy.setdefault("routing", {})["capability_router"] = router
        policy_path.write_text(json.dumps(policy, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        applied["localChatMaxChars"] = f"{local_chat_max} -> {new_local_chat_max}"

    report = _render_report(policy, event_stats, suggestions, applied, snapshot_path)
    report_path.write_text(report, encoding="utf-8")
    _write_json(
        json_path,
        {
            "generated_at": _utc_now(),
            "applied": applied,
            "suggestions": suggestions,
            "event_stats": event_stats,
            "token_snapshot": str(snapshot_path),
        },
    )
    return EvolverResult(report_path=report_path, json_path=json_path, applied=applied, suggestions=suggestions)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate bounded Grokness evolution recommendations.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--apply-safe", action="store_true", help="Apply bounded routing threshold changes.")
    args = parser.parse_args()

    result = run(Path(args.repo_root).resolve(), apply_safe=args.apply_safe)
    print(
        json.dumps(
            {
                "report_path": str(result.report_path),
                "json_path": str(result.json_path),
                "applied": result.applied,
                "suggestions": result.suggestions,
            },
            indent=2,
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
