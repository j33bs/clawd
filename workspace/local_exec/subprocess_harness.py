from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any


class SubprocessPolicyError(RuntimeError):
    pass


def _ensure_within_repo(repo_root: Path, cwd: Path) -> None:
    repo_resolved = repo_root.resolve()
    cwd_resolved = cwd.resolve()
    if repo_resolved == cwd_resolved:
        return
    if repo_resolved not in cwd_resolved.parents:
        raise SubprocessPolicyError("cwd outside repo root")


def _reject_shell_like(argv: list[str]) -> None:
    if len(argv) == 1 and (" " in argv[0] or any(token in argv[0] for token in (";", "&&", "||", "|", "$", "`"))):
        raise SubprocessPolicyError("shell-like command string is not allowed")


def run_argv(
    argv: list[str],
    *,
    repo_root: Path,
    cwd: Path | None = None,
    timeout_sec: int = 60,
    env_allowlist: list[str] | None = None,
    max_output_bytes: int = 262144,
) -> dict[str, Any]:
    if not isinstance(argv, list) or not argv:
        raise SubprocessPolicyError("argv must be a non-empty list")
    if any(not isinstance(item, str) for item in argv):
        raise SubprocessPolicyError("argv entries must be strings")
    _reject_shell_like(argv)

    run_cwd = (cwd or repo_root).resolve()
    _ensure_within_repo(repo_root, run_cwd)

    env: dict[str, str] = {"PATH": os.environ.get("PATH", "")}
    if env_allowlist:
        for key in env_allowlist:
            if key in os.environ:
                env[key] = os.environ[key]

    start = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            cwd=str(run_cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
            shell=False,
        )
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        proc = exc
        timed_out = True

    duration_ms = int((time.monotonic() - start) * 1000)
    stdout = getattr(proc, "stdout", "") or ""
    stderr = getattr(proc, "stderr", "") or ""
    if len(stdout.encode("utf-8", errors="ignore")) > max_output_bytes:
        stdout = stdout.encode("utf-8")[:max_output_bytes].decode("utf-8", errors="replace")
    if len(stderr.encode("utf-8", errors="ignore")) > max_output_bytes:
        stderr = stderr.encode("utf-8")[:max_output_bytes].decode("utf-8", errors="replace")

    return {
        "argv": argv,
        "returncode": None if timed_out else proc.returncode,
        "timed_out": timed_out,
        "duration_ms": duration_ms,
        "stdout": stdout,
        "stderr": stderr,
    }
