from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def find_repo_root() -> Path | None:
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        return Path(proc.stdout.strip())

    cur = Path(__file__).resolve()
    for parent in [cur] + list(cur.parents):
        if (parent / ".git").exists():
            return parent
    return None


def main() -> int:
    py_exe = sys.executable or ""
    py_ver = sys.version.replace("\n", " ").strip()
    which_py3 = shutil.which("python3") or ""

    print(f"PYTHON_EXE={py_exe}")
    print(f"PYTHON_VER={py_ver}")
    print(f"PYTHON3_WHICH={which_py3}")

    if not py_exe or "python3" not in os.path.basename(py_exe):
        print("WARN=running under a non-python3 executable", file=sys.stderr)

    repo = find_repo_root()
    if repo is None:
        print("ERROR=repo root not found", file=sys.stderr)
        return 2

    base_cfg = repo / "pipelines" / "system1_trading.yaml"
    overlay_cfg = repo / "pipelines" / "system1_trading.features.yaml"

    print(f"REPO_ROOT={repo}")
    print(f"BASE_CONFIG={base_cfg}")
    print(f"BASE_CONFIG_EXISTS={1 if base_cfg.exists() else 0}")
    print(f"FEATURES_OVERLAY={overlay_cfg}")
    print(f"FEATURES_OVERLAY_EXISTS={1 if overlay_cfg.exists() else 0}")

    if not base_cfg.exists():
        print("ERROR=base config missing; expected pipelines/system1_trading.yaml", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
