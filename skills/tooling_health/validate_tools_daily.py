#!/usr/bin/env python3
"""Daily tool/MCP validator with offline-state and heartbeat reporting hooks."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import traceback
from pathlib import Path
from urllib import error, request


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def utc_stamp() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def append_error(path: Path, *, tool_id: str, name: str, detail: str, stack_trace: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"[{utc_stamp()}] tool_id={tool_id} check={name}\n")
        fh.write(detail.rstrip() + "\n")
        fh.write("traceback:\n")
        fh.write(stack_trace.rstrip() + "\n")
        fh.write("---\n")


def http_check(item: dict) -> tuple[bool, dict, str]:
    url = str(item.get("url", "")).strip()
    if not url:
        return False, {"error": "missing url"}, "ValueError: missing url"
    timeout = int(item.get("timeout_sec", 5) or 5)
    req = request.Request(url, method="GET")
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            status = int(getattr(resp, "status", 200))
            sample = resp.read(200).decode("utf-8", errors="replace")
            ok = 200 <= status < 400
            info = {"status": status, "body_sample": sample, "url": url}
            if ok:
                return True, info, ""
            return False, info, f"HTTPError: status={status}"
    except Exception as exc:  # noqa: BLE001
        return False, {"url": url, "error": str(exc)}, traceback.format_exc()


def command_check(item: dict) -> tuple[bool, dict, str]:
    cmd = item.get("command")
    if not isinstance(cmd, list) or not cmd:
        return False, {"error": "missing command"}, "ValueError: missing command"
    timeout = int(item.get("timeout_sec", 20) or 20)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except Exception:  # noqa: BLE001
        return False, {"command": cmd}, traceback.format_exc()

    info = {
        "command": cmd,
        "returncode": int(proc.returncode),
        "stdout": proc.stdout[-800:],
        "stderr": proc.stderr[-800:],
    }
    if proc.returncode == 0:
        return True, info, ""
    synthetic_stack = "".join(traceback.format_stack(limit=12))
    return False, info, synthetic_stack


def run_check(item: dict) -> tuple[bool, dict, str]:
    kind = str(item.get("kind", "")).strip().lower()
    if kind == "http":
        return http_check(item)
    if kind == "command":
        return command_check(item)
    return False, {"error": f"unsupported kind: {kind}"}, "ValueError: unsupported kind"


def update_offline_state(state_path: Path, failures: list[dict], ttl_hours: int) -> dict:
    state = read_json(state_path, {"schema": 1, "offline": {}})
    if not isinstance(state, dict):
        state = {"schema": 1, "offline": {}}
    offline = state.get("offline")
    if not isinstance(offline, dict):
        offline = {}

    now = utc_now()
    # Drop expired entries first.
    retained = {}
    for tool_id, row in offline.items():
        if not isinstance(row, dict):
            continue
        expires_at = str(row.get("expires_at", "")).replace("Z", "+00:00")
        try:
            expiry = dt.datetime.fromisoformat(expires_at)
        except ValueError:
            continue
        if expiry > now:
            retained[tool_id] = row
    offline = retained

    for entry in failures:
        tool_id = entry["tool_id"]
        first_failed = offline.get(tool_id, {}).get("first_failed_at", utc_stamp())
        offline[tool_id] = {
            "tool_id": tool_id,
            "check": entry["name"],
            "kind": entry["kind"],
            "first_failed_at": first_failed,
            "last_failed_at": utc_stamp(),
            "expires_at": (now + dt.timedelta(hours=max(1, ttl_hours))).isoformat().replace("+00:00", "Z"),
            "reason": entry["detail"],
        }

    state = {
        "schema": 1,
        "updated_at": utc_stamp(),
        "ttl_hours": max(1, ttl_hours),
        "offline": offline,
    }
    write_json(state_path, state)
    return state


def write_heartbeat_notice(path: Path, *, offline_state: dict, run_failures: list[dict]) -> None:
    offline = offline_state.get("offline", {}) if isinstance(offline_state, dict) else {}
    if not isinstance(offline, dict):
        offline = {}
    if not offline:
        if path.exists():
            path.unlink()
        return

    lines = [
        "# Tool Validation Alert",
        "",
        f"- Generated: {utc_stamp()}",
        f"- Current offline tool count: {len(offline)}",
        "",
        "## Offline Tools",
    ]
    for tool_id, row in sorted(offline.items()):
        if not isinstance(row, dict):
            continue
        lines.append(
            f"- `{tool_id}` until {row.get('expires_at', 'unknown')} ({row.get('reason', 'no reason captured')})"
        )

    if run_failures:
        lines.extend(["", "## Newly Failed In This Run"])
        for item in run_failures:
            lines.append(f"- `{item['tool_id']}`: {item['detail']}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily tool/MCP validator.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument(
        "--targets",
        default=str(Path(__file__).with_name("tool_validation_targets.json")),
        help="JSON file with checks array",
    )
    parser.add_argument("--offline-ttl-hours", type=int, default=24)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    targets_path = Path(args.targets).resolve()
    runtime_dir = repo_root / "workspace" / "state_runtime" / "tool_validation"
    error_log = runtime_dir / "tool_error.log"
    state_path = runtime_dir / "offline_tools.json"
    runtime_config_path = runtime_dir / "tool_routing_overrides.json"
    notice_path = runtime_dir / "heartbeat_notice.md"
    latest_report_path = runtime_dir / "latest_report.json"

    targets = read_json(targets_path, {"checks": []})
    checks = targets.get("checks", []) if isinstance(targets, dict) else []
    if not isinstance(checks, list):
        checks = []

    results: list[dict] = []
    failures: list[dict] = []
    for raw in checks:
        item = raw if isinstance(raw, dict) else {}
        name = str(item.get("name", "unnamed"))
        tool_id = str(item.get("tool_id", name))
        kind = str(item.get("kind", "unknown"))
        ok, info, stack_trace = run_check(item)
        detail = info.get("error") if isinstance(info, dict) else None
        if not detail:
            detail = f"{kind} check {'ok' if ok else 'failed'}"
        row = {
            "name": name,
            "tool_id": tool_id,
            "kind": kind,
            "ok": bool(ok),
            "info": info,
            "detail": str(detail),
        }
        results.append(row)
        if not ok:
            failure = {
                "name": name,
                "tool_id": tool_id,
                "kind": kind,
                "detail": str(detail),
            }
            failures.append(failure)
            append_error(
                error_log,
                tool_id=tool_id,
                name=name,
                detail=str(detail),
                stack_trace=stack_trace or "no traceback captured",
            )

    offline_state = update_offline_state(state_path, failures, args.offline_ttl_hours)

    offline_tools = sorted((offline_state.get("offline") or {}).keys())
    write_json(
        runtime_config_path,
        {
            "schema": 1,
            "generated_at": utc_stamp(),
            "offline_tools": offline_tools,
            "source": str(state_path),
        },
    )
    write_heartbeat_notice(notice_path, offline_state=offline_state, run_failures=failures)

    summary = {
        "generated_at": utc_stamp(),
        "targets_path": str(targets_path),
        "checks_total": len(results),
        "checks_failed": len(failures),
        "results": results,
        "offline_tools": offline_tools,
        "error_log": str(error_log),
        "state_path": str(state_path),
        "runtime_config_path": str(runtime_config_path),
        "heartbeat_notice_path": str(notice_path),
    }
    write_json(latest_report_path, summary)
    print(json.dumps(summary, ensure_ascii=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
