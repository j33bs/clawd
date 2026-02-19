#!/usr/bin/env python3
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


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


def main():
    checks = {
        "vllm": check_vllm(),
        "disk": check_disk(),
        "memory": check_memory(),
        "openclaw_gateway": check_gateway(),
        "security_audit": check_security_audit(),
    }
    overall_pass = all(c.get("pass") for c in checks.values())
    payload = {
        "timestamp": now_iso(),
        "overall_pass": overall_pass,
        "checks": checks,
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
