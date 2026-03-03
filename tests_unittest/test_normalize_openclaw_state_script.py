import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "normalize_openclaw_state.sh"


def _run(cmd, cwd: Path, env=None):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False, env=env)


def _init_repo(root: Path) -> None:
    r = _run(["git", "init"], root)
    assert r.returncode == 0, r.stderr
    r = _run(["git", "config", "user.email", "tests@example.invalid"], root)
    assert r.returncode == 0, r.stderr
    r = _run(["git", "config", "user.name", "Unit Tests"], root)
    assert r.returncode == 0, r.stderr


class TestNormalizeOpenclawStateScript(unittest.TestCase):
    def test_removes_non_regular_state_path(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir(parents=True, exist_ok=True)
            _init_repo(repo)
            bad = repo / ".openclaw" / "workspace-state.json"
            bad.mkdir(parents=True, exist_ok=True)

            r = _run(["bash", str(SCRIPT)], repo)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse(bad.exists())

    def test_initializes_state_file_when_opted_in(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir(parents=True, exist_ok=True)
            _init_repo(repo)
            target = repo / "_target.txt"
            target.write_text("x\n", encoding="utf-8")
            stray = repo / ".openclaw" / "workspace-state.json"
            stray.parent.mkdir(parents=True, exist_ok=True)

            made_symlink = False
            if hasattr(os, "symlink"):
                try:
                    os.symlink(str(target), str(stray))
                    made_symlink = True
                except OSError:
                    made_symlink = False
            if not made_symlink:
                stray.mkdir(parents=True, exist_ok=True)

            env = os.environ.copy()
            env["OPENCLAW_STATE_FILE_INIT"] = "1"
            r = _run(["bash", str(SCRIPT)], repo, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(stray.exists())
            self.assertTrue(stat.S_ISREG(stray.stat().st_mode))
            self.assertEqual(stray.read_text(encoding="utf-8").strip(), "{}")


if __name__ == "__main__":
    unittest.main()
