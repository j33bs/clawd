#!/usr/bin/env python3
"""
Diagnose why `openclaw status` hangs using timeboxed, read-only checks.
"""
import argparse
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def run_cmd(args, timeout_sec=8, cwd=None):
    started = time.time()
    try:
        proc = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        elapsed_ms = int((time.time() - started) * 1000)
        return {
            "command": " ".join(args),
            "exit_code": proc.returncode,
            "timed_out": False,
            "elapsed_ms": elapsed_ms,
            "stdout": (proc.stdout or "").strip(),
            "stderr": (proc.stderr or "").strip(),
        }
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.time() - started) * 1000)
        return {
            "command": " ".join(args),
            "exit_code": None,
            "timed_out": True,
            "elapsed_ms": elapsed_ms,
            "stdout": (exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "").strip() if isinstance(exc.stderr, str) else "",
        }
    except Exception as exc:
        elapsed_ms = int((time.time() - started) * 1000)
        return {
            "command": " ".join(args),
            "exit_code": None,
            "timed_out": False,
            "elapsed_ms": elapsed_ms,
            "stdout": "",
            "stderr": str(exc),
        }


def truncate(text, size=300):
    if not text:
        return ""
    return text if len(text) <= size else text[:size] + "..."


def diagnose(results, has_openclaw):
    notes = []
    if not has_openclaw:
        notes.append("openclaw binary not found on PATH. Root cause is likely PATH/install.")
        return notes

    by_cmd = {r["command"]: r for r in results}
    status = by_cmd.get("openclaw status")
    deep = by_cmd.get("openclaw status --deep")
    js = by_cmd.get("openclaw status --json")
    gateway_status = by_cmd.get("openclaw gateway status")

    if status and status["timed_out"] and deep and deep["timed_out"]:
        notes.append("Both `openclaw status` and `openclaw status --deep` timed out. Likely CLI/daemon wait, lock contention, or backend hang.")
    if status and status["timed_out"] and not (status["stdout"] or status["stderr"]):
        notes.append("No stdout/stderr before timeout, suggesting a blocked call before normal status rendering.")
    if js and js["exit_code"] not in (0, None):
        lower = (js.get("stderr", "") + " " + js.get("stdout", "")).lower()
        if "unknown" in lower or "option" in lower:
            notes.append("`openclaw status --json` appears unsupported in this CLI version.")
    if gateway_status:
        gateway_text = f"{gateway_status.get('stdout', '')}\n{gateway_status.get('stderr', '')}".lower()
        if "launchagent (loaded)" in gateway_text and "not listening" in gateway_text:
            notes.append(
                "Gateway service is loaded but not listening on its port; use launchctl kickstart and re-check curl."
            )
        if "gateway start blocked: set gateway.mode=local" in gateway_text:
            notes.append(
                "Gateway start is blocked by config: set gateway.mode=local or use --allow-unconfigured explicitly."
            )
    if not notes:
        notes.append("No single root cause proven; inspect command stderr excerpts and optional strace output.")
    return notes


def main():
    parser = argparse.ArgumentParser(description="Diagnose openclaw status hangs")
    parser.add_argument("--timeout", type=int, default=8, help="Per-command timeout seconds")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[2]
    tmp = repo / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = tmp / f"openclaw_status_diag_{ts}.md"
    trace_path = tmp / f"openclaw_status_strace_{ts}.log"

    openclaw_path = shutil.which("openclaw")
    strace_path = shutil.which("strace")

    checks = [
        ["openclaw", "--version"],
        ["openclaw", "status"],
        ["openclaw", "status", "--deep"],
        ["openclaw", "status", "--json"],
        ["openclaw", "gateway", "status"],
    ]

    results = []
    for cmd in checks:
        if openclaw_path is None:
            results.append(
                {
                    "command": " ".join(cmd),
                    "exit_code": None,
                    "timed_out": False,
                    "elapsed_ms": 0,
                    "stdout": "",
                    "stderr": "openclaw not on PATH",
                }
            )
            continue
        results.append(run_cmd(cmd, timeout_sec=args.timeout, cwd=str(repo)))

    strace_result = None
    if openclaw_path and strace_path:
        strace_cmd = [
            "strace",
            "-tt",
            "-f",
            "-o",
            str(trace_path),
            "-e",
            "trace=network,process,file",
            "openclaw",
            "status",
        ]
        strace_result = run_cmd(strace_cmd, timeout_sec=args.timeout, cwd=str(repo))
    else:
        strace_result = {
            "command": "strace openclaw status",
            "exit_code": None,
            "timed_out": False,
            "elapsed_ms": 0,
            "stdout": "",
            "stderr": "strace unavailable" if not strace_path else "openclaw unavailable",
        }

    env_names = sorted([k for k in os.environ.keys() if k.upper().startswith("OPENCLAW_")])

    lines = [
        f"# OpenClaw Status Hang Diagnostics {ts}",
        "",
        "## Environment",
        f"- cwd: `{repo}`",
        f"- PATH entries: `{len(os.environ.get('PATH', '').split(os.pathsep))}`",
        f"- openclaw_on_path: `{str(openclaw_path is not None).lower()}`",
        f"- openclaw_path: `{openclaw_path or 'not found'}`",
        f"- strace_available: `{str(strace_path is not None).lower()}`",
        "- OPENCLAW_* env names:",
    ]
    if env_names:
        for name in env_names:
            lines.append(f"  - `{name}`")
    else:
        lines.append("  - none")

    lines.extend(
        [
            "",
            "## Command Results",
            "| Command | Exit | Timed Out | Elapsed ms | Stdout (excerpt) | Stderr (excerpt) |",
            "|---|---:|---|---:|---|---|",
        ]
    )
    for row in results:
        lines.append(
            "| {cmd} | {exit_code} | {timed_out} | {elapsed_ms} | {stdout} | {stderr} |".format(
                cmd=row["command"],
                exit_code=row["exit_code"] if row["exit_code"] is not None else "null",
                timed_out=str(row["timed_out"]).lower(),
                elapsed_ms=row["elapsed_ms"],
                stdout=truncate(row["stdout"]).replace("|", "\\|"),
                stderr=truncate(row["stderr"]).replace("|", "\\|"),
            )
        )

    lines.extend(
        [
            "",
            "## Strace (best effort)",
            f"- command: `{strace_result['command']}`",
            f"- exit_code: `{strace_result['exit_code']}`",
            f"- timed_out: `{str(strace_result['timed_out']).lower()}`",
            f"- elapsed_ms: `{strace_result['elapsed_ms']}`",
            f"- stderr: `{truncate(strace_result['stderr'])}`",
            f"- trace_file: `{trace_path if trace_path.exists() else 'not generated'}`",
        ]
    )

    lines.extend(["", "## Diagnosis", *[f"- {n}" for n in diagnose(results, openclaw_path is not None)]])

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
