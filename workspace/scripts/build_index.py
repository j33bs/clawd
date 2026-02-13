#!/usr/bin/env python3
"""
Deterministic index builder (System-1).

Writes:
- workspace/INDEX.json: list of {path, sha256, bytes}
- workspace/INDEX.md: bullet list of paths

The index is intentionally content-light (hashes only). It also excludes
known SECRET/EPHEMERAL paths to avoid accidental leakage.
"""

import hashlib
import json
import os
from pathlib import Path


INCLUDE_SUFFIXES = {
    ".md",
    ".py",
    ".js",
    ".ts",
    ".ps1",
    ".sh",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".txt",
}

EXCLUDE_DIR_NAMES = {
    ".git",
    ".tmp",
    ".workspace_artifacts",
    "__pycache__",
    "node_modules",
    "tmp",
}

EXCLUDE_FILE_NAMES = {
    "secrets.env",
    ".env",
    ".env.local",
    ".envrc",
}

EXCLUDE_SUFFIXES = {
    ".bak",
    ".log",
    ".sqlite",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
}


def _resolve_repo_root(start: Path) -> Path | None:
    current = start
    for _ in range(10):
        if (current / ".git").exists():
            return current
        current = current.parent
    return None


def _is_secret_or_ephemeral(rel_posix: str) -> bool:
    # SECRET or ephemeral (BOUNDARIES.md) patterns.
    if rel_posix == "secrets.env":
        return True
    if rel_posix.startswith("credentials/"):
        return True
    if rel_posix.startswith("devices/"):
        return True
    if rel_posix.startswith("identity/"):
        return True
    if rel_posix.startswith("memory/"):
        return True
    if rel_posix.startswith("workspace/memory/"):
        return True
    if rel_posix.startswith("workspace/.state/"):
        return True
    if rel_posix.startswith("agents/") and rel_posix.endswith("/agent/auth-profiles.json"):
        return True
    if rel_posix.startswith("workspace.bak_"):
        return True
    if rel_posix.startswith("workspace.bak_") or "/workspace.bak_" in rel_posix:
        return True
    if rel_posix.endswith(".git.bak") or "/.git.bak/" in rel_posix:
        return True
    if rel_posix.endswith(".env.local") or rel_posix.endswith(".env"):
        return True
    return False


def _sha256_file(path: Path) -> tuple[str, int] | None:
    try:
        data = path.read_bytes()
    except Exception:
        return None
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest(), len(data)


def build_index(repo_root: Path) -> list[dict]:
    items: list[dict] = []
    out_json = (repo_root / "workspace" / "INDEX.json").resolve()
    out_md = (repo_root / "workspace" / "INDEX.md").resolve()

    for dirpath, dirnames, filenames in os.walk(repo_root):
        dir_path = Path(dirpath)
        # Deterministic traversal
        dirnames.sort()
        filenames.sort()

        # Prune excluded dirs in-place
        pruned = []
        for d in dirnames:
            if d in EXCLUDE_DIR_NAMES:
                continue
            if d.startswith("workspace.bak_"):
                continue
            if d.endswith(".git.bak"):
                continue
            pruned.append(d)
        dirnames[:] = pruned

        for fn in filenames:
            if fn in EXCLUDE_FILE_NAMES:
                continue
            p = dir_path / fn
            if p.resolve() in (out_json, out_md):
                continue
            if p.suffix in EXCLUDE_SUFFIXES:
                continue
            if p.suffix.lower() not in INCLUDE_SUFFIXES:
                continue

            try:
                rel = p.relative_to(repo_root).as_posix()
            except Exception:
                continue

            if _is_secret_or_ephemeral(rel):
                continue

            hashed = _sha256_file(p)
            if not hashed:
                continue
            sha, size = hashed
            items.append({"path": rel, "sha256": sha, "bytes": size})

    items.sort(key=lambda x: x["path"])
    return items


def main():
    repo_root = _resolve_repo_root(Path(__file__).resolve())
    if repo_root is None:
        raise SystemExit("FAIL: could not locate repo root (no .git found)")

    workspace_dir = repo_root / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    items = build_index(repo_root)
    (workspace_dir / "INDEX.json").write_text(json.dumps(items, indent=2) + "\n", encoding="utf-8")
    (workspace_dir / "INDEX.md").write_text("\n".join(f"- {it['path']}" for it in items) + "\n", encoding="utf-8")
    print(f"ok: wrote {len(items)} entries to workspace/INDEX.json and workspace/INDEX.md")


if __name__ == "__main__":
    main()

