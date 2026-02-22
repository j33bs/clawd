from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any


class SubprocessPolicyError(RuntimeError):
    pass


def _repo_realpath(repo_root: Path) -> str:
    return os.path.realpath(str(repo_root))


def _ensure_within_repo(repo_root: Path, target: Path) -> None:
    repo_resolved = _repo_realpath(repo_root)
    target_resolved = os.path.realpath(str(target))
    if target_resolved == repo_resolved:
        return
    if not target_resolved.startswith(repo_resolved + os.sep):
        raise SubprocessPolicyError("path_rejected:outside_repo")


def resolve_repo_path(repo_root: Path, user_path: str, *, must_exist: bool = False) -> Path:
    if not isinstance(user_path, str) or not user_path.strip():
        raise SubprocessPolicyError("path_rejected:empty")
    candidate = Path(user_path)
    if candidate.is_absolute():
        raise SubprocessPolicyError("path_rejected:absolute")
    if ".." in candidate.parts:
        raise SubprocessPolicyError("path_rejected:parent_ref")

    resolved = (repo_root / candidate).resolve()
    _ensure_within_repo(repo_root, resolved)
    if must_exist and not resolved.exists():
        raise SubprocessPolicyError("path_rejected:not_found")
    return resolved


def _reject_shell_like(argv: list[str]) -> None:
    if len(argv) == 1 and (" " in argv[0] or any(token in argv[0] for token in (";", "&&", "||", "|", "$", "`"))):
        raise SubprocessPolicyError("argv_rejected:shell_like")


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
        raise SubprocessPolicyError("argv_rejected:empty")
    if any(not isinstance(item, str) for item in argv):
        raise SubprocessPolicyError("argv_rejected:not_strings")
    _reject_shell_like(argv)

    run_cwd = cwd.resolve() if cwd is not None else repo_root.resolve()
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

    stdout_bytes = len(stdout.encode("utf-8", errors="ignore"))
    stderr_bytes = len(stderr.encode("utf-8", errors="ignore"))
    stdout_truncated = stdout_bytes > max_output_bytes
    stderr_truncated = stderr_bytes > max_output_bytes

    if stdout_truncated:
        stdout = stdout.encode("utf-8")[:max_output_bytes].decode("utf-8", errors="replace")
    if stderr_truncated:
        stderr = stderr.encode("utf-8")[:max_output_bytes].decode("utf-8", errors="replace")

    return {
        "argv": argv,
        "returncode": None if timed_out else proc.returncode,
        "timed_out": timed_out,
        "duration_ms": duration_ms,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_bytes": stdout_bytes,
        "stderr_bytes": stderr_bytes,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
    }
