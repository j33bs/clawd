#!/usr/bin/env python3
"""Daily tool/MCP validator with offline-state and heartbeat reporting hooks."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path
from urllib import error, request


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def utc_stamp() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def contract_signal(kind: str, meta: dict | None = None) -> None:
    root = Path(__file__).resolve().parents[2]
    signal_path = os.environ.get("OPENCLAW_CONTRACT_SIGNALS_PATH") or str(
        root / "workspace" / "state_runtime" / "contract" / "signals" / "activity.jsonl"
    )
    target = Path(signal_path)
    payload = {
        "ts": utc_stamp(),
        "kind": kind,
        "meta": meta or {},
    }
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, sort_keys=True) + "\n")
    except OSError:
        pass


def gpu_policy_allowed(*, repo_root: Path, tool_id: str) -> dict:
    policy_script = repo_root / "workspace" / "scripts" / "contract_policy.py"
    if not policy_script.exists():
        return {"allowed": True, "reason": "policy_script_missing"}

    try:
        proc = subprocess.run(
            [sys.executable, str(policy_script), "gpu-allowed", "--tool-id", tool_id],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception:
        return {"allowed": True, "reason": "policy_check_error"}

    payload: dict = {}
    try:
        payload = json.loads((proc.stdout or "").strip() or "{}")
    except json.JSONDecodeError:
        payload = {}

    if not isinstance(payload, dict):
        payload = {}
    if "allowed" not in payload:
        payload["allowed"] = True
    if "reason" not in payload:
        payload["reason"] = "policy_unknown"
    return payload


def gpu_last_activity_mark(*, repo_root: Path, tool_id: str, source: str) -> None:
    target = repo_root / "workspace" / "state_runtime" / "gpu" / "last_activity.json"
    try:
        current = read_json(target, {})
        if not isinstance(current, dict):
            current = {}
        current[tool_id] = {"ts": utc_stamp(), "source": source}
        write_json(target, current)
    except OSError:
        pass


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


def load_checks_from_inventory(path: Path) -> list[dict]:
    """
    Supported target shapes (backward-compatible):
    1) {"checks":[{...}]}
    2) {"targets":[{...}]}
    3) [{...}]
    4) {"<tool_id>": {...}, ...}
    """
    data = read_json(path, {})
    raw_checks: list[dict] = []

    if isinstance(data, dict):
        if isinstance(data.get("checks"), list):
            raw_checks = [item for item in data["checks"] if isinstance(item, dict)]
        elif isinstance(data.get("targets"), list):
            raw_checks = [item for item in data["targets"] if isinstance(item, dict)]
        else:
            for key, value in data.items():
                if not isinstance(value, dict):
                    continue
                item = dict(value)
                item.setdefault("tool_id", item.get("id") or key)
                raw_checks.append(item)
    elif isinstance(data, list):
        raw_checks = [item for item in data if isinstance(item, dict)]

    out: list[dict] = []
    for raw in raw_checks:
        item = dict(raw)
        tool_id = str(item.get("tool_id") or item.get("id") or item.get("name") or "").strip()
        if not tool_id:
            continue
        item["tool_id"] = tool_id
        out.append(item)
    return out


def classify_probe_error(detail: str) -> str:
    text = (detail or "").lower()
    if text.startswith("policy:"):
        return "policy"
    if "refused" in text or "econnrefused" in text:
        return "refused"
    if "timed out" in text or "timeout" in text:
        return "timeout"
    if "missing url" in text:
        return "misconfigured"
    return "error"


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
    kind = str(item.get("kind") or item.get("type") or "").strip().lower()
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
            "offline_class": str(entry.get("offline_class", "FAULT")),
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
        klass = row.get("offline_class", "FAULT")
        lines.append(
            f"- `{tool_id}` [{klass}] until {row.get('expires_at', 'unknown')} ({row.get('reason', 'no reason captured')})"
        )

    if run_failures:
        lines.extend(["", "## Newly Failed In This Run"])
        for item in run_failures:
            lines.append(f"- `{item['tool_id']}`: {item['detail']}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    default_targets = os.environ.get("OPENCLAW_TOOL_INV") or str(Path(__file__).with_name("tool_validation_targets.json"))
    parser = argparse.ArgumentParser(description="Daily tool/MCP validator.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument(
        "--targets",
        default=default_targets,
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

    checks = load_checks_from_inventory(targets_path)
    contract_signal("tool_call", {"source": "validate_tools_daily"})

    results: list[dict] = []
    probe_report: dict[str, dict] = {}
    failures: list[dict] = []
    for raw in checks:
        item = raw if isinstance(raw, dict) else {}
        name = str(item.get("name", "unnamed"))
        tool_id = str(item.get("tool_id", name))
        kind = str(item.get("kind") or item.get("type") or "unknown")
        ok, info, stack_trace = run_check(item)
        detail = info.get("error") if isinstance(info, dict) else None
        if not detail:
            detail = f"{kind} check {'ok' if ok else 'failed'}"

        offline_class = "FAULT"
        if not ok and tool_id == "coder_vllm.models":
            policy = gpu_policy_allowed(repo_root=repo_root, tool_id=tool_id)
            if isinstance(info, dict):
                info = dict(info)
                info["policy_gate"] = policy
            if not bool(policy.get("allowed")):
                offline_class = "POLICY"
                detail = f"POLICY:{policy.get('reason') or 'policy_blocked'}"
            else:
                ensure_path = repo_root / "workspace" / "scripts" / "ensure_coder_vllm_up.py"
                if ensure_path.exists():
                    try:
                        ensured = subprocess.run(
                            [sys.executable, str(ensure_path)],
                            capture_output=True,
                            text=True,
                            timeout=40,
                            check=False,
                        )
                        ensure_payload = {}
                        try:
                            ensure_payload = json.loads((ensured.stdout or "").strip() or "{}")
                        except json.JSONDecodeError:
                            ensure_payload = {}
                        if ensured.returncode == 0:
                            ok2, info2, stack2 = run_check(item)
                            if ok2:
                                ok = True
                                info = dict(info2) if isinstance(info2, dict) else {"info": info2}
                                info["recovered_via"] = "ensure_coder_vllm_up"
                                info["policy_gate"] = policy
                                detail = "recovered via ensure_coder_vllm_up"
                                stack_trace = stack2
                        else:
                            ensured_class = str(ensure_payload.get("offline_class") or "").upper()
                            ensured_reason = str(ensure_payload.get("reason") or "").strip()
                            if ensured_class == "POLICY":
                                offline_class = "POLICY"
                                detail = f"POLICY:{ensured_reason or 'contract_or_gpu_lock'}"
                            elif ensured_class:
                                offline_class = ensured_class
                            if isinstance(info, dict) and ensure_payload:
                                info = dict(info)
                                info["ensure_result"] = ensure_payload
                                info["policy_gate"] = policy
                    except subprocess.TimeoutExpired:
                        detail = "FAULT:ensure_coder_vllm_up_timeout"

        row = {
            "name": name,
            "tool_id": tool_id,
            "kind": kind,
            "ok": bool(ok),
            "info": info,
            "detail": str(detail),
        }
        if ok and tool_id == "coder_vllm.models":
            gpu_last_activity_mark(repo_root=repo_root, tool_id=tool_id, source="validator_ok")
        results.append(row)
        probe_entry = {
            "tool_id": tool_id,
            "name": name,
            "kind": kind,
            "url": item.get("url") or item.get("endpoint") or item.get("baseUrl"),
            "host": item.get("host"),
            "port": item.get("port"),
            "probe": {
                "ok": bool(ok),
                "detail": str(detail),
                "info": info,
            },
        }
        if not ok:
            probe_entry["reason_class"] = classify_probe_error(str(detail))
        probe_report[tool_id] = probe_entry
        if not ok:
            failure = {
                "name": name,
                "tool_id": tool_id,
                "kind": kind,
                "offline_class": offline_class,
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
    normalized_probe_path = runtime_dir / "probe_report_normalized.json"
    write_json(normalized_probe_path, probe_report)

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
        "normalized_probe_path": str(normalized_probe_path),
    }
    write_json(latest_report_path, summary)
    print(json.dumps(summary, ensure_ascii=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
