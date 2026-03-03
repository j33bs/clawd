from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_PATH = REPO_ROOT / "workspace" / "scripts" / "preflight_check.py"


def _load_preflight_module():
    spec = importlib.util.spec_from_file_location("preflight_check", PREFLIGHT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)


class TestPreflightUntrackedAllowlist(unittest.TestCase):
    def setUp(self) -> None:
        self.preflight = _load_preflight_module()

    def test_ignored_state_runtime_file_does_not_stop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_git_repo(repo)
            (repo / ".git" / "info" / "exclude").write_text(
                "workspace/state_runtime/\n",
                encoding="utf-8",
            )
            target = repo / "workspace" / "state_runtime" / "sample.tmp"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("ignored artifact\n", encoding="utf-8")

            result = self.preflight._auto_ingest_allowlisted_teammate_untracked(repo)

            self.assertIsNone(result)

    def test_untracked_non_allowlisted_file_stops_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_git_repo(repo)
            bad = repo / "tmp_disallowed.txt"
            bad.write_text("x\n", encoding="utf-8")

            result = self.preflight._auto_ingest_allowlisted_teammate_untracked(repo)

            self.assertIsInstance(result, dict)
            assert isinstance(result, dict)
            self.assertTrue(result.get("stopped"))
            self.assertEqual(result.get("error"), "untracked_disallowed")
            self.assertIn("tmp_disallowed.txt", result.get("disallowed", []))


if __name__ == "__main__":
    unittest.main()
