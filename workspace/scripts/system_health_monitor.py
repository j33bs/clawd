#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from event_envelope import append_envelope, make_envelope


DISK_WARN_THRESHOLD = 80.0
MEM_WARN_THRESHOLD = 80.0
AUDIT_STALE_HOURS = 24 * 7


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_cmd(cmd: list[str], timeout: int = 8):
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return cp.returncode, cp.stdout.strip(), cp.stderr.strip()
    except Exception as exc:
        return 1, "", str(exc)


def check_vllm() -> dict:
    url = "http://127.0.0.1:8001/v1/models"
    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=4) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = getattr(resp, "status", 200)
            passed = (200 <= status < 300) and ("\"data\"" in body or "\"object\"" in body)
            return {
                "pass": passed,
                "url": url,
                "http_status": status,
                "response_sample": body[:160],
            }
    except HTTPError as exc:
        return {"pass": False, "url": url, "error": f"HTTP {exc.code}: {exc.reason}"}
    except URLError as exc:
        return {"pass": False, "url": url, "error": str(exc.reason)}
    except Exception as exc:
        return {"pass": False, "url": url, "error": str(exc)}

def _coder_log_path() -> Path:
    return Path(
        os.environ.get("OPENCLAW_VLLM_CODER_LOG_PATH")
        or (Path.home() / ".local" / "state" / "openclaw" / "vllm-coder.log")
    ).expanduser()


def _replay_log_path() -> Path:
    return Path(
        os.environ.get("OPENCLAW_REPLAY_LOG_PATH")
        or (Path.home() / ".local" / "share" / "openclaw" / "replay" / "replay.jsonl")
    ).expanduser()


def _event_log_path() -> Path:
    return Path(
        os.environ.get("OPENCLAW_EVENT_ENVELOPE_LOG_PATH")
        or (Path.home() / ".local" / "share" / "openclaw" / "events" / "gate_health.jsonl")
    ).expanduser()


def _detect_coder_degraded_reason() -> str:
    path = _coder_log_path()
    try:
        if not path.exists():
            return "UNKNOWN"
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in reversed(lines[-20:]):
            if "VRAM_GUARD_BLOCKED" in line:
                if "reason=VRAM_LOW" in line:
                    return "VRAM_LOW"
                return "VRAM_GUARD_BLOCKED"
    except PermissionError:
        return "PERMISSION_DENIED"
    except Exception:
        return "UNKNOWN"
    return "UNKNOWN"


def check_coder_vllm() -> dict:
    base = os.environ.get("OPENCLAW_VLLM_CODER_BASE_URL", "http://127.0.0.1:8002/v1")
    url = base.rstrip("/") + "/models"
    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=4) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = getattr(resp, "status", 200)
            passed = (200 <= status < 300) and ("\"data\"" in body or "\"object\"" in body)
            return {
                "pass": passed,
                "status": "UP" if passed else "DOWN",
                "coder_degraded_reason": "OK" if passed else "UNKNOWN",
                "url": url,
                "http_status": status,
                "response_sample": body[:160],
            }
    except PermissionError:
        return {
            "pass": True,
            "status": "UNKNOWN",
            "coder_degraded_reason": "PERMISSION_DENIED",
            "url": url,
            "reason": "permission_denied",
        }
    except Exception as exc:
        reason = _detect_coder_degraded_reason()
        status = "DEGRADED" if reason in {"VRAM_LOW", "VRAM_GUARD_BLOCKED"} else "DOWN"
        return {
            "pass": status in {"UP", "DEGRADED"},
            "status": status,
            "coder_degraded_reason": reason,
            "url": url,
            "error": str(exc),
        }


def check_replay_log_writable() -> dict:
    path = _replay_log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8"):
            pass
        return {"pass": True, "status": "WRITABLE", "path": str(path)}
    except PermissionError:
        return {"pass": True, "status": "UNKNOWN", "reason": "permission_denied", "path": str(path)}
    except Exception as exc:
        return {"pass": False, "status": "NOACCESS", "reason": f"{type(exc).__name__}:{exc}", "path": str(path)}


def check_pairing_canary() -> dict:
    guard = Path(__file__).resolve().parent / "check_gateway_pairing_health.sh"
    if not guard.exists():
        return {"pass": False, "status": "UNHEALTHY", "reason": "pairing_guard_missing", "path": str(guard)}
    rc, out, err = run_cmd([str(guard)], timeout=20)
    if rc == 0:
        return {"pass": True, "status": "OK", "path": str(guard), "summary": "\n".join(out.splitlines()[:3])}
    return {
        "pass": False,
        "status": "UNHEALTHY",
        "path": str(guard),
        "return_code": rc,
        "summary": "\n".join((out or err).splitlines()[:3]),
    }


def check_disk() -> dict:
    total, used, free = shutil.disk_usage("/")
    used_pct = (used / total) * 100 if total else 0.0
    return {
        "pass": used_pct <= DISK_WARN_THRESHOLD,
        "threshold_percent": DISK_WARN_THRESHOLD,
        "used_percent": round(used_pct, 2),
        "total_gb": round(total / (1024 ** 3), 2),
        "free_gb": round(free / (1024 ** 3), 2),
    }


def check_memory() -> dict:
    meminfo = {}
    with open("/proc/meminfo", "r", encoding="utf-8") as f:
        for line in f:
            key, val = line.split(":", 1)
            meminfo[key.strip()] = int(val.strip().split()[0])  # KiB

    total = meminfo.get("MemTotal", 0)
    available = meminfo.get("MemAvailable", 0)
    used = max(total - available, 0)
    used_pct = (used / total) * 100 if total else 0.0

    return {
        "pass": used_pct <= MEM_WARN_THRESHOLD,
        "threshold_percent": MEM_WARN_THRESHOLD,
        "used_percent": round(used_pct, 2),
        "total_gb": round(total / (1024 ** 2), 2),
        "available_gb": round(available / (1024 ** 2), 2),
    }


def check_gateway() -> dict:
    rc, out, err = run_cmd(["openclaw", "gateway", "status"], timeout=10)
    lower = out.lower()
    running = ("runtime: running" in lower) and ("rpc probe: ok" in lower)
    return {
        "pass": rc == 0 and running,
        "return_code": rc,
        "running_detected": running,
        "summary": "\n".join(out.splitlines()[:6]),
        "notes": err or None,
    }


def _extract_last_audit_ts(path: Path):
    if not path.exists():
        return None
    try:
        # Read last non-empty line efficiently
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = obj.get("ts")
            if ts:
                return ts
    except Exception:
        return None
    return None


def _parse_iso(ts: str):
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def check_security_audit() -> dict:
    candidates = [
        Path("/home/jeebs/.openclaw/logs/config-audit.jsonl"),
        Path("/home/jeebs/.openclaw_backups/openclaw-state-20260217-222359/logs/config-audit.jsonl"),
    ]

    chosen = None
    last_ts = None
    for p in candidates:
        ts = _extract_last_audit_ts(p)
        if ts:
            chosen = p
            last_ts = ts
            break

    if not last_ts:
        return {
            "pass": False,
            "error": "No security audit log timestamp found",
            "checked_paths": [str(p) for p in candidates],
        }

    dt = _parse_iso(last_ts)
    if not dt:
        return {
            "pass": False,
            "error": f"Unparseable timestamp: {last_ts}",
            "path": str(chosen),
        }

    age_hours = (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600.0
    return {
        "pass": age_hours <= AUDIT_STALE_HOURS,
        "last_run": dt.astimezone(timezone.utc).isoformat(),
        "age_hours": round(age_hours, 2),
        "stale_after_hours": AUDIT_STALE_HOURS,
        "path": str(chosen),
    }


def build_actionable_hints(checks: dict) -> list[dict]:
    hints: list[dict] = []
    vllm = checks.get("vllm", {})
    if vllm and not vllm.get("pass", True):
        hints.append(
            {
                "component": "vllm",
                "reason": str(vllm.get("error") or "ASSISTANT_DOWN"),
                "remedy": "run `systemctl --user status openclaw-vllm.service` and verify `curl -sf http://127.0.0.1:8001/health`",
            }
        )

    coder = checks.get("coder_vllm", {})
    if coder.get("status") != "UP":
        reason = str(coder.get("coder_degraded_reason") or "UNAVAILABLE")
        if reason == "VRAM_LOW":
            remedy = "reduce GPU contention or lower `VLLM_CODER_MIN_FREE_VRAM_MB` before restarting coder lane"
        else:
            remedy = "run `systemctl --user status openclaw-vllm-coder.service` and inspect `journalctl --user -u openclaw-vllm-coder.service -n 80`"
        hints.append({"component": "coder_vllm", "reason": reason, "remedy": remedy})

    pairing = checks.get("pairing_canary", {})
    if pairing.get("status") == "UNHEALTHY":
        hints.append(
            {
                "component": "pairing_canary",
                "reason": str(pairing.get("reason") or "PAIRING_UNHEALTHY"),
                "remedy": "run `workspace/scripts/check_gateway_pairing_health.sh` and `openclaw pairing list --json`",
            }
        )

    replay = checks.get("replay_log", {})
    if replay.get("status") == "NOACCESS":
        hints.append(
            {
                "component": "replay_log",
                "reason": str(replay.get("reason") or "NOACCESS"),
                "remedy": "run `mkdir -p ~/.local/share/openclaw/replay && chmod -R u+rwX ~/.local/share/openclaw`",
            }
        )

    plugin = checks.get("plugin_allowlist", {})
    if plugin and not plugin.get("pass", True):
        hints.append(
            {
                "component": "plugin_allowlist",
                "reason": str(plugin.get("reason") or "PLUGIN_ALLOWLIST_VIOLATION"),
                "remedy": "update `workspace/config/openclaw.json` plugin allowlist and restart OpenClaw",
            }
        )

    gateway = checks.get("openclaw_gateway", {})
    if gateway and not gateway.get("pass", True):
        hints.append(
            {
                "component": "openclaw_gateway",
                "reason": str(gateway.get("notes") or "GATEWAY_UNHEALTHY")[:240],
                "remedy": "run `openclaw doctor --repair` then `openclaw gateway status`",
            }
        )

    return hints


def emit_health_event(*, overall_pass: bool, actionable_hints: list[dict], checks: dict) -> dict:
    corr_id = f"health_{uuid.uuid4().hex[:10]}"
    if not overall_pass:
        event = "health.fail"
        severity = "ERROR"
    elif actionable_hints:
        event = "health.degraded"
        severity = "WARN"
    else:
        event = "health.ok"
        severity = "INFO"
    envelope = make_envelope(
        event=event,
        severity=severity,
        component="system_health_monitor",
        corr_id=corr_id,
        details={
            "overall_pass": bool(overall_pass),
            "hints_count": len(actionable_hints),
            "actionable_hints": actionable_hints,
            "coder_status": checks.get("coder_vllm", {}).get("status"),
            "pairing_status": checks.get("pairing_canary", {}).get("status"),
            "replay_status": checks.get("replay_log", {}).get("status"),
        },
    )
    out = append_envelope(_event_log_path(), envelope)
    return {"event": event, "severity": severity, "corr_id": corr_id, "write": out}


def main():
    checks = {
        "vllm": check_vllm(),
        "coder_vllm": check_coder_vllm(),
        "replay_log": check_replay_log_writable(),
        "pairing_canary": check_pairing_canary(),
        "disk": check_disk(),
        "memory": check_memory(),
        "openclaw_gateway": check_gateway(),
        "security_audit": check_security_audit(),
    }
    overall_pass = all(c.get("pass") for c in checks.values())
    actionable_hints = build_actionable_hints(checks)
    event_status = emit_health_event(overall_pass=overall_pass, actionable_hints=actionable_hints, checks=checks)
    payload = {
        "timestamp": now_iso(),
        "overall_pass": overall_pass,
        "checks": checks,
        "actionable_hints": actionable_hints,
        "event_envelope": event_status,
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
