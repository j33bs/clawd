#!/usr/bin/env python3
"""Runtime identity helper for Dali tool payload sanitization."""

import importlib.util
import json
import os
from pathlib import Path


def _resolve_repo_root(start: Path) -> Path | None:
    current = start
    for _ in range(8):
        if (current / ".git").exists():
            return current
        current = current.parent
    return None


def _git_sha(repo_root: Path | None) -> str:
    if not repo_root:
        return "unknown"
    head = repo_root / ".git" / "HEAD"
    try:
        raw = head.read_text(encoding="utf-8").strip()
        if raw.startswith("ref:"):
            ref = raw.split(" ", 1)[1].strip()
            ref_file = repo_root / ".git" / ref
            if ref_file.exists():
                return ref_file.read_text(encoding="utf-8").strip()[:12]
            return "unknown"
        return raw[:12]
    except Exception:
        return "unknown"


def _module_path(name: str, path: Path) -> str:
    spec = importlib.util.spec_from_file_location(name, str(path))
    if not spec or not spec.loader:
        return "unknown"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return str(Path(module.__file__).resolve())


def main() -> int:
    this_file = Path(__file__).resolve()
    repo_root = _resolve_repo_root(this_file)
    scripts_dir = this_file.parent
    info = {
        "policy_router_module_path": _module_path("policy_router", scripts_dir / "policy_router.py"),
        "tool_payload_sanitizer_module_path": _module_path(
            "tool_payload_sanitizer", scripts_dir / "tool_payload_sanitizer.py"
        ),
        "git_sha": _git_sha(repo_root),
        "strict_tool_payload_enabled": str(os.environ.get("OPENCLAW_STRICT_TOOL_PAYLOAD", "")).strip().lower()
        in {"1", "true", "yes"},
        "openclaw_strict_tool_payload_raw": os.environ.get("OPENCLAW_STRICT_TOOL_PAYLOAD", ""),
    }
    print(json.dumps(info, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

