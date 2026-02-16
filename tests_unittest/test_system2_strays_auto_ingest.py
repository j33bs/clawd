import importlib.util
import os
import stat
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path


def _load_preflight_check_module():
    repo_root = Path(__file__).resolve().parents[1]
    mod_path = repo_root / "workspace" / "scripts" / "preflight_check.py"
    spec = importlib.util.spec_from_file_location("preflight_check", str(mod_path))
    assert spec and spec.loader, f"Failed to load module spec for {mod_path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(cmd, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)


def _init_repo(repo: Path) -> None:
    r = _run(["git", "init"], repo)
    assert r.returncode == 0, r.stderr
    r = _run(["git", "config", "user.email", "teammate@example.invalid"], repo)
    assert r.returncode == 0, r.stderr
    r = _run(["git", "config", "user.name", "Teammate Ingest Bot"], repo)
    assert r.returncode == 0, r.stderr


def _write_sync_script(overlay: Path) -> Path:
    sync = overlay / "sync_into_repo.sh"
    sync.write_text(
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        ': "${OPENCLAW_ROOT:?}"\n'
        f'touch "{overlay}/.sync_ran"\n',
        encoding="utf-8",
    )
    sync.chmod(sync.stat().st_mode | stat.S_IXUSR)
    return sync


class TestSystem2StraysAutoIngest(unittest.TestCase):
    def test_moves_known_strays_out_of_repo_then_governance_ingest_can_run(self):
        preflight_check = _load_preflight_check_module()
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            overlay = Path(td) / "overlay"
            home = Path(td) / "home"
            repo.mkdir(parents=True, exist_ok=True)
            overlay.mkdir(parents=True, exist_ok=True)
            home.mkdir(parents=True, exist_ok=True)
            _init_repo(repo)

            # Known governance docs at repo root.
            for name in preflight_check._KNOWN_GOV_ROOT_STRAYS:
                (repo / name).write_text(f"dummy {name}\n", encoding="utf-8")

            # Strays that should be auto-moved out of the repo.
            (repo / ".openclaw").mkdir(parents=True, exist_ok=True)
            (repo / ".openclaw" / "workspace-state.json").write_text("{}", encoding="utf-8")
            (repo / "moltbook_registration_plan.md").write_text("plan\n", encoding="utf-8")

            sync = _write_sync_script(overlay)
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["CLAWD_GOV_OVERLAY_DIR"] = str(overlay)
            env["CLAWD_GOV_OVERLAY_SYNC"] = str(sync)

            with unittest.mock.patch.dict(os.environ, env, clear=False):
                s0 = preflight_check._auto_ingest_known_system2_strays(repo)

                self.assertIsNotNone(s0)
                self.assertFalse(s0.get("stopped"))

                # Strays should no longer exist in the repo.
                self.assertFalse((repo / ".openclaw" / "workspace-state.json").exists())
                self.assertFalse((repo / "moltbook_registration_plan.md").exists())

                # They should exist under ~/.openclaw.
                self.assertTrue((home / ".openclaw" / "workspace-state.json").exists())
                self.assertTrue((home / ".openclaw" / "ingest" / "moltbook_registration_plan.md").exists())

                # Governance ingest should now see the exact-set at repo root and proceed.
                s1 = preflight_check._auto_ingest_known_gov_root_strays(repo)
                self.assertIsNotNone(s1)
                self.assertFalse(s1.get("stopped"))

            self.assertTrue((overlay / ".sync_ran").exists())

    def test_non_regular_file_stops_fail_closed(self):
        preflight_check = _load_preflight_check_module()
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            home = Path(td) / "home"
            repo.mkdir(parents=True, exist_ok=True)
            home.mkdir(parents=True, exist_ok=True)
            _init_repo(repo)

            # Make one known stray a directory (non-file). git status does not reliably
            # enumerate empty directories, so the ingest must rely on filesystem lstat
            # checks (not just parsed status output).
            (repo / ".openclaw" / "workspace-state.json").mkdir(parents=True, exist_ok=True)
            # Ensure there is at least one untracked file under the parent so status
            # sees the directory, but it still won't list the known stray child path.
            (repo / ".openclaw" / "_other.txt").write_text("x\n", encoding="utf-8")

            untracked = preflight_check._untracked_paths(repo)
            self.assertIn(".openclaw/_other.txt", untracked)
            self.assertNotIn(".openclaw/workspace-state.json", untracked)

            env = os.environ.copy()
            env["HOME"] = str(home)
            with unittest.mock.patch.dict(os.environ, env, clear=False):
                s0 = preflight_check._auto_ingest_known_system2_strays(repo)

            self.assertIsNotNone(s0)
            self.assertTrue(s0.get("stopped"))
            self.assertEqual(s0.get("error"), "known_stray_non_regular_file")
            self.assertEqual(s0.get("kind"), "dir")

            # Nothing should be created under ~/.openclaw.
            self.assertFalse((home / ".openclaw" / "workspace-state.json").exists())

    def test_symlink_known_stray_stops_fail_closed_even_if_parent_is_untracked(self):
        preflight_check = _load_preflight_check_module()
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            home = Path(td) / "home"
            repo.mkdir(parents=True, exist_ok=True)
            home.mkdir(parents=True, exist_ok=True)
            _init_repo(repo)

            if not hasattr(os, "symlink"):
                self.skipTest("symlink unsupported on this platform")

            (repo / ".openclaw").mkdir(parents=True, exist_ok=True)
            target = repo / "_target.txt"
            target.write_text("x\n", encoding="utf-8")

            stray = repo / ".openclaw" / "workspace-state.json"
            try:
                os.symlink(str(target), str(stray))
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation not permitted")

            r = _run(["git", "status", "--porcelain=v1", "-uall"], repo)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("?? .openclaw/", r.stdout)

            env = os.environ.copy()
            env["HOME"] = str(home)
            with unittest.mock.patch.dict(os.environ, env, clear=False):
                s0 = preflight_check._auto_ingest_known_system2_strays(repo)

            self.assertIsNotNone(s0)
            self.assertTrue(s0.get("stopped"))
            self.assertEqual(s0.get("error"), "known_stray_non_regular_file")
            self.assertEqual(s0.get("kind"), "symlink")


if __name__ == "__main__":
    unittest.main()
