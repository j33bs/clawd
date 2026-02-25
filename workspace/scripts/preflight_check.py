#!/usr/bin/env python3
"""
Preflight checks for environment prerequisites.
Fails fast with actionable guidance.
"""
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def _resolve_repo_root(start: Path):
    current = start
    for _ in range(8):
        if (current / ".git").exists():
            return current
        current = current.parent
    return None


_env_root = os.environ.get("OPENCLAW_ROOT")
_file_root = _resolve_repo_root(Path(__file__).resolve())
_cwd_root = _resolve_repo_root(Path.cwd())
BASE_DIR = Path(_env_root) if _env_root else (_file_root or _cwd_root or Path("C:/Users/heath/.openclaw"))
POLICY_FILE = BASE_DIR / "workspace" / "policy" / "llm_policy.json"
SYSTEM_MAP_FILE = BASE_DIR / "workspace" / "policy" / "system_map.json"
OPENCLAW_WORKSPACE_FILE = BASE_DIR / "workspace" / "config" / "openclaw.json"
OPENCLAW_LEGACY_FILE = BASE_DIR / "openclaw.json"
OPENCLAW_FILE = (
    Path(os.environ["OPENCLAW_CONFIG_PATH"]).expanduser()
    if os.environ.get("OPENCLAW_CONFIG_PATH")
    else (OPENCLAW_WORKSPACE_FILE if OPENCLAW_WORKSPACE_FILE.exists() else OPENCLAW_LEGACY_FILE)
)
PAIRING = BASE_DIR / "credentials" / "telegram-pairing.json"

sys.path.insert(0, str((BASE_DIR / "workspace" / "scripts").resolve()))
sys.path.insert(0, str((BASE_DIR / "workspace").resolve()))

try:
    import requests  # noqa: F401
    REQUESTS_OK = True
except Exception:
    REQUESTS_OK = False

try:
    from policy_router import PolicyRouter
except Exception:
    PolicyRouter = None

try:
    from itc_pipeline.allowlist import resolve_allowlist, AllowlistConfigError
except Exception:
    resolve_allowlist = None
    AllowlistConfigError = None

ALLOWLIST_EXAMPLE = (
    "ALLOWED_CHAT_IDS=-1001369282532,-1001700695156,-1002117631304,-1001445373305"
)

# Known governance docs that sometimes appear untracked at repo root.
# Policy: if (and only if) the untracked repo-root set matches this list exactly,
# auto-ingest them into the operator's governance overlay and sync into the repo.
_KNOWN_GOV_ROOT_STRAYS = (
    "AGENTS.md",
    "HEARTBEAT.md",
    "IDENTITY.md",
    "SOUL.md",
    "TOOLS.md",
    "USER.md",
)

# Known local-only root artifacts that must not trigger governance auto-ingest.
# Keep this set narrow and explicit to avoid weakening fail-closed behavior.
_IGNORABLE_ROOT_UNTRACKED = (
    ".claude",
    ".claude/",
    ".openclaw",
    ".openclaw/",
    ".openclaw/workspace-state.json",
    ".DS_Store",
)

# Teammate-ingest allowlist (strict, fail-closed).
# Only these untracked paths are eligible for auto-ingest.
_TEAMMATE_ALLOWLIST_PREFIX = "core/integration/"
_TEAMMATE_ALLOWLIST_EXTS = (".js", ".mjs", ".ts")
_TEAMMATE_MAX_BYTES = 256 * 1024

# Known non-governance strays that should never live untracked in the repo.
# Policy: if present as untracked, auto-move them into the operator's home OpenClaw
# directory (backup-first) so preflight can continue fail-closed on *other* drift.
_KNOWN_SYSTEM2_STRAYS = (
    "moltbook_registration_plan.md",
    ".openclaw/workspace-state.json",
)

_ALLOWED_UNTRACKED_PREFIXES = (
    "workspace/state_runtime/",
    "workspace/research/pdfs/",
    "memory/literature/",
    ".worktrees/",
    "workspace/audit/",
)
_ALLOWED_UNTRACKED_PATTERNS = (
    re.compile(r"^memory/\d{4}-\d{2}-\d{2}\.md$"),
    re.compile(r"^docs/AUDIT_.*\.md$"),
)


def fail(msg, fixes, failures):
    failures.append({"msg": msg, "fixes": fixes})


def warn(msg, warns):
    warns.append(msg)


def _network_preflight_enabled() -> bool:
    return os.getenv("OPENCLAW_PREFLIGHT_NETWORK", "0") == "1"


def load_json(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def normalize_node_id(raw_value, system_map):
    if not isinstance(system_map, dict):
        return "dali"
    nodes = system_map.get("nodes") or {}
    default_id = str(system_map.get("default_node_id") or "dali")

    if raw_value is None:
        return default_id

    needle = str(raw_value).strip().lower()
    if not needle:
        return default_id

    for node_id, node_cfg in nodes.items():
        aliases = node_cfg.get("aliases") if isinstance(node_cfg, dict) else None
        values = aliases if isinstance(aliases, list) else [node_id]
        for alias in values:
            if str(alias).strip().lower() == needle:
                return node_id
    return default_id


def _run_git_status_porcelain_z(repo_root: Path) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain=v1", "-z", "-uall"],
        capture_output=True,
        check=False,
    )
    return proc.stdout or b""


def _untracked_paths(repo_root: Path) -> List[str]:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    out: List[str] = []
    for path in (proc.stdout or "").splitlines():
        norm = path.replace("\\", "/").strip().strip("/")
        if not norm:
            continue
        out.append(norm)
    return sorted(set(out))


def _untracked_repo_root_files(repo_root: Path) -> List[str]:
    out: List[str] = []
    for norm in _untracked_paths(repo_root):
        # Only repo-root files (no slashes).
        if "/" in norm:
            continue
        out.append(norm)
    return sorted(set(out))


def _is_allowed_untracked_path(rel: str) -> bool:
    p = rel.replace("\\", "/").strip("/")
    if not p:
        return False
    for prefix in _ALLOWED_UNTRACKED_PREFIXES:
        if p.startswith(prefix):
            return True
    for pattern in _ALLOWED_UNTRACKED_PATTERNS:
        if pattern.match(p):
            return True
    return False


def _is_ignorable_root_untracked(rel: str) -> bool:
    p = rel.replace("\\", "/").strip("/")
    if not p:
        return False
    normalized_allow = {x.replace("\\", "/").strip("/") for x in _IGNORABLE_ROOT_UNTRACKED}
    if p in normalized_allow:
        return True
    if p.startswith(".claude/") and ".claude" in normalized_allow:
        return True
    if p.startswith(".openclaw/") and ".openclaw" in normalized_allow:
        return True
    return False


def _ts_suffix() -> str:
    # Stable, filesystem-safe, local time.
    return time.strftime("%Y%m%d-%H%M%S")


def _is_allowlisted_teammate_path(rel_posix: str) -> bool:
    p = rel_posix.replace("\\", "/").lstrip("/")
    if not p.startswith(_TEAMMATE_ALLOWLIST_PREFIX):
        return False
    return p.endswith(_TEAMMATE_ALLOWLIST_EXTS)


def _is_regular_file_no_symlink(abs_path: Path) -> bool:
    if abs_path.is_symlink():
        return False
    return abs_path.is_file()


def _read_bytes_for_scan(abs_path: Path) -> bytes:
    # Safety: size gate is enforced before calling this.
    return abs_path.read_bytes()


def _scan_token_like(abs_path: Path) -> List[str]:
    """
    Conservative token-like scanning. Returns rule IDs only (never match strings).
    """
    try:
        raw = _read_bytes_for_scan(abs_path)
    except Exception:
        return ["rule_unreadable"]

    # Treat as text for scanning; ignore invalid bytes.
    text = raw.decode("utf-8", errors="ignore")

    rules: List[tuple[str, str]] = [
        ("rule_openai_sk", r"\bsk-[A-Za-z0-9]{20,}\b"),
        ("rule_groq_gsk", r"\bgsk_[A-Za-z0-9]{20,}\b"),
        ("rule_bearer", r"\bBearer\s+[A-Za-z0-9._-]{20,}\b"),
        ("rule_pem_key", r"-----BE" r"GIN [A-Z ]+PRI" r"VATE KE" r"Y-----"),
        ("rule_aws_access_key", r"\bAKIA[0-9A-Z]{16}\b"),
        ("rule_slack_token", r"\bxox[baprs]-[0-9]{10,}-[0-9]{10,}-[A-Za-z0-9]{24,}\b"),
        ("rule_github_pat", r"\bghp_[A-Za-z0-9]{20,}\b"),
    ]

    hits: List[str] = []
    for rule_id, pat in rules:
        try:
            if re.search(pat, text):
                hits.append(rule_id)
        except Exception:
            continue
    return hits


def _quarantine_paths(repo_root: Path, rel_paths: List[str]) -> Dict[str, Any]:
    """
    Move paths out of the repo into a quarantine directory, preserving structure.
    Never deletes.

    Env override (useful for tests):
      - CLAWD_PREFLIGHT_QUARANTINE_DIR (base dir; a timestamped subdir is created)
    """
    base = os.environ.get("CLAWD_PREFLIGHT_QUARANTINE_DIR")
    if base:
        base_dir = Path(base).expanduser()
    else:
        base_dir = Path("/tmp")

    stamp = _ts_suffix()
    root = base_dir / f"openclaw-quarantine-{stamp}"
    moved: List[str] = []

    for rel in rel_paths:
        rel_norm = rel.replace("\\", "/").lstrip("/")
        src = repo_root / rel_norm
        if not src.exists():
            continue
        dest = root / rel_norm
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        moved.append(rel_norm)

    return {"quarantine_root": str(root), "moved": moved}


def _git(repo_root: Path, args: List[str], capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=capture,
        text=True,
        check=False,
    )


def _auto_ingest_allowlisted_teammate_untracked(repo_root: Path) -> Optional[Dict[str, Any]]:
    """
    Stage B — Teammate code ingest (NEW):
      - allowlist only core/integration/**/*.(js|mjs|ts)
      - validate safety gates (regular file, size, binary, token-like scan)
      - if safe: create a topic branch, stage, run gates, commit
      - if gates fail: quarantine and STOP (non-zero)
      - if any other untracked drift exists: STOP (preserve behavior)

    Env overrides (tests/harness):
      - CLAWD_PREFLIGHT_SKIP_NPM_TESTS=1
      - CLAWD_PREFLIGHT_SKIP_UNITTESTS=1
    """
    untracked = _untracked_paths(repo_root)
    if not untracked:
        return None

    allowlisted = [p for p in untracked if _is_allowlisted_teammate_path(p)]
    disallowed = [
        p
        for p in untracked
        if p not in allowlisted and not _is_allowed_untracked_path(p)
    ]
    if disallowed:
        print("STOP (unrelated workspace drift detected)")
        print("untracked_disallowed_paths:")
        for p in disallowed:
            print(f"- {p}")
        return {"stopped": True, "error": "untracked_disallowed", "disallowed": disallowed}

    if not allowlisted:
        return None

    # Validate all allowlisted files before staging anything (atomicity).
    safety_fail: Dict[str, List[str]] = {}
    for rel in allowlisted:
        abs_path = repo_root / rel
        if not abs_path.exists():
            safety_fail.setdefault(rel, []).append("missing")
            continue
        if abs_path.is_symlink():
            print("STOP (teammate auto-ingest requires regular files; no symlinks/dirs)")
            print(f"path={rel}")
            return {"stopped": True, "error": "non_regular_file", "path": rel, "kind": "symlink"}
        if not abs_path.is_file():
            print("STOP (teammate auto-ingest requires regular files; no symlinks/dirs)")
            print(f"path={rel}")
            return {"stopped": True, "error": "non_regular_file", "path": rel, "kind": "non_file"}

        size = abs_path.stat().st_size
        if size > _TEAMMATE_MAX_BYTES:
            safety_fail.setdefault(rel, []).append("size_limit")
            continue

        raw = _read_bytes_for_scan(abs_path)
        if b"\x00" in raw:
            safety_fail.setdefault(rel, []).append("binary_nul")
            continue

        rules = _scan_token_like(abs_path)
        if rules:
            safety_fail.setdefault(rel, []).extend(rules)

    if safety_fail:
        # Quarantine only the failing paths to keep the worktree safe.
        bad = sorted(safety_fail.keys())
        q = _quarantine_paths(repo_root, bad)
        print("STOP (teammate auto-ingest safety scan failed)")
        print("flagged_paths:")
        for p in bad:
            print(f"- {p}: {','.join(safety_fail[p])}")
        print(f"quarantine_root={q.get('quarantine_root')}")
        return {"stopped": True, "error": "safety_scan_failed", "flagged": safety_fail, "quarantine": q}

    # Fail closed if operator already has staged changes; avoid accidentally committing them.
    cached = _git(repo_root, ["diff", "--cached", "--name-only"])
    if cached.returncode != 0:
        print("STOP (teammate auto-ingest could not inspect index state)")
        return {"stopped": True, "error": "git_diff_cached_failed"}
    if (cached.stdout or "").strip():
        print("STOP (teammate auto-ingest requires empty index; staged changes present)")
        return {"stopped": True, "error": "staged_changes_present"}

    # Create a topic branch and stage the allowlisted files.
    stamp = _ts_suffix()
    branch = f"teammate/ingest-{stamp}"

    # Create and switch (candidate PR branch).
    r = _git(repo_root, ["checkout", "-b", branch])
    if r.returncode != 0:
        print("STOP (teammate auto-ingest failed to create branch)")
        return {"stopped": True, "error": "git_checkout_failed", "stderr": (r.stderr or "").strip()}

    r = _git(repo_root, ["add", "--", *allowlisted])
    if r.returncode != 0:
        print("STOP (teammate auto-ingest failed to stage files)")
        return {"stopped": True, "error": "git_add_failed"}

    # Gates (no stdout/stderr streaming; avoid accidental leakage).
    skip_unittest = os.environ.get("CLAWD_PREFLIGHT_SKIP_UNITTESTS") == "1"
    skip_npm = os.environ.get("CLAWD_PREFLIGHT_SKIP_NPM_TESTS") == "1"

    if not skip_unittest:
        p = subprocess.run(
            [sys.executable, "-m", "unittest", "-q"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if p.returncode != 0:
            _git(repo_root, ["reset"])
            q = _quarantine_paths(repo_root, allowlisted)
            print("STOP (teammate auto-ingest gate failed: python unittest)")
            print(f"exit_code={p.returncode}")
            print(f"quarantine_root={q.get('quarantine_root')}")
            return {"stopped": True, "error": "gate_failed_unittest", "exit_code": p.returncode, "quarantine": q}

    if not skip_npm:
        p = subprocess.run(
            ["npm", "test"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if p.returncode != 0:
            _git(repo_root, ["reset"])
            q = _quarantine_paths(repo_root, allowlisted)
            print("STOP (teammate auto-ingest gate failed: npm test)")
            print(f"exit_code={p.returncode}")
            print(f"quarantine_root={q.get('quarantine_root')}")
            return {"stopped": True, "error": "gate_failed_npm_test", "exit_code": p.returncode, "quarantine": q}

    # Commit the staged allowlisted files.
    msg = "chore(teammate): ingest untracked allowlisted files (auto-gated)"
    r = _git(repo_root, ["commit", "-m", msg])
    if r.returncode != 0:
        print("STOP (teammate auto-ingest failed to commit)")
        return {"stopped": True, "error": "git_commit_failed"}

    head = _git(repo_root, ["rev-parse", "--short", "HEAD"])
    commit_short = (head.stdout or "").strip() if head.returncode == 0 else "unknown"
    print("teammate_auto_ingest: ok")
    print(f"branch={branch}")
    print(f"commit={commit_short}")
    print("files:")
    for p in allowlisted:
        print(f"- {p}")
    return {"stopped": False, "branch": branch, "commit": commit_short, "files": allowlisted}


def _auto_ingest_known_gov_root_strays(repo_root: Path) -> Optional[Dict[str, Any]]:
    """
    Returns a summary dict if ingestion was performed, else None.

    Env overrides (useful for tests/smoke checks):
      - CLAWD_GOV_OVERLAY_DIR
      - CLAWD_GOV_OVERLAY_SYNC
    """
    root_untracked_raw = set(_untracked_repo_root_files(repo_root))
    root_untracked = set(p for p in root_untracked_raw if not _is_ignorable_root_untracked(p))
    if not root_untracked:
        return None

    known = set(_KNOWN_GOV_ROOT_STRAYS)

    unexpected = sorted(p for p in root_untracked if p not in known)
    if unexpected:
        print("STOP (unrelated workspace drift detected)")
        print("untracked_repo_root_files_non_ignorable:")
        for p in sorted(root_untracked):
            print(f"- {p}")
        return {"stopped": True, "root_untracked": sorted(root_untracked), "unexpected": unexpected}

    known_present = sorted(p for p in known if p in root_untracked)
    if not known_present:
        return None
    if set(known_present) != known:
        missing = sorted(p for p in known if p not in root_untracked)
        print("STOP (known governance stray set is partial; exact-set required)")
        print("known_present:")
        for p in known_present:
            print(f"- {p}")
        print("known_missing:")
        for p in missing:
            print(f"- {p}")
        return {
            "stopped": True,
            "error": "known_set_partial",
            "known_present": known_present,
            "known_missing": missing,
        }

    # Fail-closed filesystem gate: detect non-regular known names even when git
    # status reports directory paths with a trailing slash.
    for name in known:
        p = repo_root / name
        if not p.exists():
            continue
        if p.is_symlink() or p.is_dir():
            kind = "symlink" if p.is_symlink() else "dir"
            print("STOP (governance auto-ingest requires regular files; no symlinks/dirs)")
            print(f"path={name}")
            return {"stopped": True, "error": "non_regular_file", "path": name, "kind": kind}

    overlay_dir = Path(
        os.environ.get("CLAWD_GOV_OVERLAY_DIR", str(Path.home() / ".clawd_governance_overlay"))
    ).expanduser()
    sync_script = Path(
        os.environ.get("CLAWD_GOV_OVERLAY_SYNC", str(overlay_dir / "sync_into_repo.sh"))
    ).expanduser()

    # Fail closed if the governance overlay is unavailable.
    if not overlay_dir.exists() or not overlay_dir.is_dir():
        print(f"FAIL: governance overlay missing: {overlay_dir}")
        print("hint=install/setup ~/.clawd_governance_overlay with sync_into_repo.sh")
        return {"stopped": True, "error": "overlay_missing", "overlay_dir": str(overlay_dir)}
    if not sync_script.exists():
        print(f"FAIL: governance overlay sync script missing: {sync_script}")
        print("hint=add executable sync_into_repo.sh under the overlay directory")
        return {"stopped": True, "error": "sync_script_missing", "sync_script": str(sync_script)}
    if not os.access(sync_script, os.X_OK):
        print(f"FAIL: governance overlay sync script not executable: {sync_script}")
        print("hint=chmod +x ~/.clawd_governance_overlay/sync_into_repo.sh")
        return {"stopped": True, "error": "sync_script_not_executable", "sync_script": str(sync_script)}

    stamp = _ts_suffix()
    quarantine_dir = overlay_dir / "quarantine" / stamp / "repo_root_governance"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    quarantined: List[str] = []

    # Validate file types with lstat (do not follow symlinks).
    for name in known_present:
        src = repo_root / name
        try:
            st = src.lstat()
        except FileNotFoundError:
            print("STOP (governance auto-ingest missing expected file)")
            print(f"path={name}")
            return {"stopped": True, "error": "missing_expected_file", "missing": name}
        except Exception:
            print("STOP (governance auto-ingest could not lstat expected file)")
            print(f"path={name}")
            return {"stopped": True, "error": "lstat_failed", "path": name}
        if stat.S_ISLNK(st.st_mode) or stat.S_ISDIR(st.st_mode):
            print("STOP (governance auto-ingest requires regular files; no symlinks/dirs)")
            print(f"path={name}")
            kind = "symlink" if stat.S_ISLNK(st.st_mode) else "dir"
            return {"stopped": True, "error": "non_regular_file", "path": name, "kind": kind}
        if not stat.S_ISREG(st.st_mode):
            print("STOP (governance auto-ingest requires regular files)")
            print(f"path={name}")
            return {"stopped": True, "error": "non_regular_file", "path": name, "kind": "non_regular"}

    # Backup-first copy into overlay quarantine; remove source only after size check.
    for name in known_present:
        src = repo_root / name
        dest = quarantine_dir / name
        shutil.copy2(str(src), str(dest))
        if not dest.exists():
            print("FAIL: governance auto-ingest backup copy missing")
            print(f"path={name}")
            return {"stopped": True, "error": "backup_missing", "path": name}
        if src.stat().st_size != dest.stat().st_size:
            print("FAIL: governance auto-ingest backup copy size mismatch")
            print(f"path={name}")
            return {"stopped": True, "error": "backup_size_mismatch", "path": name}
        quarantined.append(name)

    for name in known_present:
        src = repo_root / name
        src.unlink()

    # Do not stream stdout/stderr (avoid accidental leakage); capture and gate by exit code.
    env = os.environ.copy()
    env["OPENCLAW_ROOT"] = str(repo_root)
    proc = subprocess.run(
        ["bash", str(sync_script)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        print("FAIL: governance overlay sync script failed")
        print(f"exit_code={proc.returncode}")
        return {"stopped": True, "error": "sync_failed", "quarantine_dir": str(quarantine_dir)}

    # Sanity: ensure known repo-root governance strays are gone.
    remaining_known = sorted(name for name in known if (repo_root / name).exists())
    if remaining_known:
        print("FAIL: known repo-root governance files remain after auto-ingest")
        for p in remaining_known:
            print(f"- {p}")
        return {"stopped": True, "error": "post_ingest_known_root_remaining", "remaining": remaining_known}

    print("governance_auto_ingest: ok")
    print(f"quarantined_files={quarantined}")
    print(f"quarantine_dir={quarantine_dir}")
    return {"stopped": False, "quarantined": quarantined, "quarantine_dir": str(quarantine_dir)}


def _auto_ingest_known_system2_strays(repo_root: Path) -> Optional[Dict[str, Any]]:
    """
    System-2 drift guard helper:
      - If specific known-untracked files appear (from model/tooling drift),
        move them out of the repo into ~/.openclaw (backup-first).
      - Fail closed on non-regular files (symlinks/dirs) to avoid surprise moves.

    This is intentionally narrow (exact paths only) to preserve STOP behavior for
    unrelated drift.
    """
    # Fail-closed filesystem gate: git status may report only the parent directory
    # as untracked (e.g. "?? .openclaw/"), so always check the exact known paths
    # directly without relying on status enumeration.
    for rel in _KNOWN_SYSTEM2_STRAYS:
        abs_p = repo_root / rel
        try:
            st = abs_p.lstat()
        except FileNotFoundError:
            continue
        except Exception:
            print("STOP (fail-closed: could not lstat known stray path)")
            print(f"path={rel}")
            return {"stopped": True, "error": "lstat_failed", "path": rel}

        if stat.S_ISLNK(st.st_mode) or stat.S_ISDIR(st.st_mode):
            kind = "symlink" if stat.S_ISLNK(st.st_mode) else "dir"
            print("STOP (fail-closed: known stray path exists as dir/symlink)")
            print(f"path={rel}")
            print(f"kind={kind}")
            return {"stopped": True, "error": "known_stray_non_regular_file", "path": rel, "kind": kind}

    untracked = set(_untracked_paths(repo_root))
    if not untracked:
        return None

    targets: List[str] = []
    for p in _KNOWN_SYSTEM2_STRAYS:
        if p in untracked:
            targets.append(p)

    if not targets:
        return None

    stamp = _ts_suffix()
    home = Path.home()
    openclaw_home = (home / ".openclaw").resolve()
    ingest_dir = openclaw_home / "ingest"
    openclaw_home.mkdir(parents=True, exist_ok=True)
    ingest_dir.mkdir(parents=True, exist_ok=True)

    moved: List[Dict[str, str]] = []
    backups: List[str] = []

    # Validate full set before moving anything (atomicity).
    for rel in targets:
        src = repo_root / rel
        if not src.exists():
            # Git status said it's untracked; fail closed if it vanished.
            print("STOP (system2 stray ingest missing expected file)")
            print(f"path={rel}")
            return {"stopped": True, "error": "missing_expected_file", "missing": rel}
        if src.is_symlink() or not src.is_file():
            print("STOP (system2 stray ingest requires regular files; no symlinks/dirs)")
            print(f"path={rel}")
            kind = "symlink" if src.is_symlink() else "non_file"
            return {"stopped": True, "error": "non_regular_file", "path": rel, "kind": kind}

    for rel in targets:
        src = repo_root / rel
        # Destination policy:
        # - workspace-state.json belongs in ~/.openclaw/
        # - other docs go under ~/.openclaw/ingest/
        if rel == ".openclaw/workspace-state.json":
            dest = openclaw_home / "workspace-state.json"
        else:
            dest = ingest_dir / Path(rel).name

        if dest.exists():
            backup = dest.with_name(dest.name + f".bak-{stamp}")
            dest.rename(backup)
            backups.append(str(backup))

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        moved.append({"from": rel, "to": str(dest)})

    # Sanity: ensure these paths are no longer untracked.
    remaining = set(_untracked_paths(repo_root))
    still = [p for p in targets if p in remaining]
    if still:
        print("FAIL: known strays remain untracked after auto-ingest")
        for p in still:
            print(f"- {p}")
        return {"stopped": True, "error": "post_ingest_untracked_remaining", "moved": moved, "backups": backups}

    print("system2_stray_auto_ingest: ok")
    print("moved:")
    for m in moved:
        print(f"- {m['from']} -> {m['to']}")
    print("backups:")
    for b in backups:
        print(f"- {b}")
    return {"stopped": False, "moved": moved, "backups": backups}


def check_policy(failures):
    data = load_json(POLICY_FILE)
    if not data:
        fail("LLM policy missing or invalid", ["Ensure workspace/policy/llm_policy.json exists and is valid JSON"], failures)
        return None
    if data.get("version") != 2:
        fail("LLM policy version must be 2", ["Update workspace/policy/llm_policy.json to version 2"], failures)
    return data


def check_router(policy, failures):
    if PolicyRouter is None:
        fail("Policy router unavailable", ["Ensure workspace/scripts/policy_router.py is present and importable"], failures)
        return
    router = PolicyRouter()
    for intent in ("itc_classify", "coding"):
        status = router.intent_status(intent)
        if not status.get("available"):
            reasons = status.get("reasons", {})
            reason_text = ", ".join(f"{k}={v}" for k, v in reasons.items()) or "unknown"
            fail(
                f"No available providers for intent: {intent}",
                [
                    "Start Ollama: `ollama serve` and pull a model (e.g., `ollama pull qwen:latest`)",
                    "Ensure free-tier credentials are present (GROQ_API_KEY or Qwen OAuth profile)",
                    f"Provider reasons: {reason_text}",
                ],
                failures,
            )


def check_requests(failures, warnings):
    if not REQUESTS_OK:
        if _network_preflight_enabled():
            fail(
                "Python requests library missing",
                ["Install requests: `python3 -m pip install requests`"],
                failures,
            )
        else:
            warn(
                "Python requests library missing (network preflight disabled). "
                "Install requests: `python3 -m pip install requests`",
                warnings,
            )


def check_plugins_allowlist(failures, warnings):
    guard_script = BASE_DIR / "workspace" / "scripts" / "openclaw_config_guard.py"
    if not guard_script.exists():
        warn("plugin allowlist guard missing; skipping plugin allow checks", warnings)
        return
    cmd = [sys.executable, str(guard_script), "--strict"]
    if os.environ.get("OPENCLAW_CONFIG_PATH"):
        cmd.extend(["--config", os.environ["OPENCLAW_CONFIG_PATH"]])
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    payload_raw = (proc.stdout or "").strip()
    if proc.returncode == 0:
        return
    issues = []
    try:
        payload = json.loads(payload_raw) if payload_raw else {}
        issues = payload.get("issues") or []
    except Exception:
        issues = [payload_raw or "unknown_plugin_allowlist_error"]
    issue_text = ", ".join(str(i) for i in issues) if issues else "plugin allowlist validation failed"
    fail(
        f"plugins_not_allowlisted: {issue_text}",
        [
            "Set plugins.allow in workspace/config/openclaw.json (or OPENCLAW_CONFIG_PATH target)",
            "Allow only explicitly trusted plugin ids",
        ],
        failures,
    )


def check_telegram(failures, warnings):
    cfg = load_json(OPENCLAW_FILE) or {}
    tg = cfg.get("channels", {}).get("telegram")
    if not tg:
        return

    if resolve_allowlist is None:
        fail(
            "telegram_not_configured: Allowlist module unavailable",
            ["Ensure workspace/itc_pipeline/allowlist.py exists and is importable"],
            failures,
        )
        return

    try:
        allowlist, source, invalid, warnings_list = resolve_allowlist()
    except AllowlistConfigError as exc:
        fail(str(exc), ["Fix allowlist configuration and retry"], failures)
        return
    for warning in warnings_list:
        warn(warning, warnings)

    if invalid:
        fail(
            "telegram_not_configured: Invalid chat IDs in allowlist",
            [
                "Replace usernames with numeric chat IDs",
                "Run `python workspace/scripts/itc/telegram_list_dialogs.py` to discover IDs",
            ],
            failures,
        )
        return

    if not allowlist:
        fail(
            "telegram_not_configured: No allowed Telegram chat IDs configured. "
            "Set ALLOWED_CHAT_IDS or add allow_chat_ids to credentials/telegram-allowFrom.json. "
            f"Example: {ALLOWLIST_EXAMPLE}",
            [
                "Set ALLOWED_CHAT_IDS env var",
                "Or update credentials/telegram-allowFrom.json (allow_chat_ids)",
            ],
            failures,
        )
        return

    if tg.get("dmPolicy") == "pairing":
        pairing = load_json(PAIRING) or {}
        if not pairing.get("requests") and not allowlist:
            fail(
                "Telegram pairing is required but no paired users exist",
                [
                    "Start a DM with the bot and send /start",
                    "Verify the bot is added to the target group/channel",
                ],
                failures,
            )

    print(f"Resolved Telegram allowlist ({source}): {sorted(allowlist)}")
    warn(
        "If you see 'chat not found', start a DM with the bot and ensure the numeric chat ID is allowlisted.",
        warnings,
    )


def check_node_identity(failures, warnings):
    cfg = load_json(OPENCLAW_FILE) or {}
    system_map = load_json(SYSTEM_MAP_FILE) or {}
    default_node_id = str(system_map.get("default_node_id") or "dali")
    config_exists = OPENCLAW_FILE.exists()

    node = cfg.get("node") if isinstance(cfg.get("node"), dict) else {}
    raw_node_id = node.get("id")
    normalized = normalize_node_id(raw_node_id, system_map)

    if config_exists and not raw_node_id:
        warn(
            f"openclaw.json node.id missing; defaulting to '{default_node_id}' for compatibility",
            warnings,
        )
    elif normalized != str(raw_node_id).strip().lower():
        warn(
            f"openclaw.json node.id alias '{raw_node_id}' normalized to '{normalized}'",
            warnings,
        )


def main():
    failures = []
    warnings = []

    sys2_ingest = _auto_ingest_known_system2_strays(BASE_DIR)
    if sys2_ingest and sys2_ingest.get("stopped"):
        sys.exit(2)

    ingest = _auto_ingest_known_gov_root_strays(BASE_DIR)
    if ingest and ingest.get("stopped"):
        sys.exit(2)

    teammate = _auto_ingest_allowlisted_teammate_untracked(BASE_DIR)
    if teammate and teammate.get("stopped"):
        sys.exit(2)

    check_requests(failures, warnings)
    check_plugins_allowlist(failures, warnings)
    policy = check_policy(failures)
    if policy:
        check_router(policy, failures)
    check_node_identity(failures, warnings)
    check_telegram(failures, warnings)

    if warnings:
        print("WARNINGS:")
        for msg in warnings:
            print(f"- {msg}")
        print("")

    if failures:
        print("FAILURES:")
        for f in failures:
            print(f"- {f['msg']}")
            for fix in f["fixes"]:
                print(f"  - {fix}")
        sys.exit(1)

    print("ok")


if __name__ == "__main__":
    main()
