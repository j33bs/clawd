import io
import importlib.util
import os
import stat
import subprocess
import tempfile
import unittest
import unittest.mock
from contextlib import redirect_stdout
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


class TestGovernanceAutoIngest(unittest.TestCase):
    def test_ingests_exact_known_root_strays_and_runs_sync(self):
        preflight_check = _load_preflight_check_module()
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            overlay = Path(td) / "overlay"
            repo.mkdir(parents=True, exist_ok=True)
            overlay.mkdir(parents=True, exist_ok=True)

            r = _run(["git", "init"], repo)
            self.assertEqual(r.returncode, 0, r.stderr)

            # Create the known untracked governance files at repo root.
            for name in preflight_check._KNOWN_GOV_ROOT_STRAYS:
                (repo / name).write_text(f"dummy {name}\n", encoding="utf-8")

            # Seed an existing overlay copy to force a backup for one file.
            (overlay / "AGENTS.md").write_text("old overlay copy\n", encoding="utf-8")

            sync = overlay / "sync_into_repo.sh"
            sync.write_text(
                "#!/bin/bash\n"
                "set -euo pipefail\n"
                ': "${OPENCLAW_ROOT:?}"\n'
                'mkdir -p "${OPENCLAW_ROOT}/workspace/governance"\n'
                'touch "${OPENCLAW_ROOT}/workspace/governance/.sync_ran"\n',
                encoding="utf-8",
            )
            sync.chmod(sync.stat().st_mode | stat.S_IXUSR)

            env = os.environ.copy()
            env["CLAWD_GOV_OVERLAY_DIR"] = str(overlay)
            env["CLAWD_GOV_OVERLAY_SYNC"] = str(sync)

            buf = io.StringIO()
            with redirect_stdout(buf):
                with unittest.mock.patch.dict(os.environ, env, clear=False):
                    summary = preflight_check._auto_ingest_known_gov_root_strays(repo)

            self.assertIsNotNone(summary)
            self.assertFalse(summary.get("stopped"))
            self.assertTrue((repo / "workspace" / "governance" / ".sync_ran").exists())

            # Repo-root files should be moved out of the repo.
            for name in preflight_check._KNOWN_GOV_ROOT_STRAYS:
                self.assertFalse((repo / name).exists())
                self.assertTrue((overlay / name).exists())

            # Backup for AGENTS.md should exist (timestamped).
            backups = summary.get("backups", [])
            self.assertTrue(any(b.startswith("AGENTS.md.bak-") for b in backups), backups)
            self.assertTrue(any((overlay / b).exists() for b in backups))

    def test_partial_set_of_known_root_strays_stops_no_ingest(self):
        preflight_check = _load_preflight_check_module()
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            overlay = Path(td) / "overlay"
            repo.mkdir(parents=True, exist_ok=True)
            overlay.mkdir(parents=True, exist_ok=True)

            r = _run(["git", "init"], repo)
            self.assertEqual(r.returncode, 0, r.stderr)

            subset = list(preflight_check._KNOWN_GOV_ROOT_STRAYS)[:3]
            for name in subset:
                (repo / name).write_text(f"dummy {name}\n", encoding="utf-8")

            sync = overlay / "sync_into_repo.sh"
            sync.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
            sync.chmod(sync.stat().st_mode | stat.S_IXUSR)

            env = os.environ.copy()
            env["CLAWD_GOV_OVERLAY_DIR"] = str(overlay)
            env["CLAWD_GOV_OVERLAY_SYNC"] = str(sync)

            buf = io.StringIO()
            with redirect_stdout(buf):
                with unittest.mock.patch.dict(os.environ, env, clear=False):
                    summary = preflight_check._auto_ingest_known_gov_root_strays(repo)

            self.assertIsNotNone(summary)
            self.assertTrue(summary.get("stopped"))

            # Nothing moved.
            for name in subset:
                self.assertTrue((repo / name).exists())
                self.assertFalse((overlay / name).exists())

    def test_non_file_known_name_stops_no_ingest(self):
        preflight_check = _load_preflight_check_module()
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            overlay = Path(td) / "overlay"
            repo.mkdir(parents=True, exist_ok=True)
            overlay.mkdir(parents=True, exist_ok=True)

            r = _run(["git", "init"], repo)
            self.assertEqual(r.returncode, 0, r.stderr)

            # Create the exact set, but make one entry a directory (not a regular file).
            bad = "AGENTS.md"
            (repo / bad).mkdir(parents=True, exist_ok=True)
            for name in preflight_check._KNOWN_GOV_ROOT_STRAYS:
                if name == bad:
                    continue
                (repo / name).write_text(f"dummy {name}\n", encoding="utf-8")

            sync = overlay / "sync_into_repo.sh"
            sync.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
            sync.chmod(sync.stat().st_mode | stat.S_IXUSR)

            env = os.environ.copy()
            env["CLAWD_GOV_OVERLAY_DIR"] = str(overlay)
            env["CLAWD_GOV_OVERLAY_SYNC"] = str(sync)

            buf = io.StringIO()
            with redirect_stdout(buf):
                with unittest.mock.patch.dict(os.environ, env, clear=False):
                    summary = preflight_check._auto_ingest_known_gov_root_strays(repo)

            self.assertIsNotNone(summary)
            self.assertTrue(summary.get("stopped"))

            # Nothing moved.
            for name in preflight_check._KNOWN_GOV_ROOT_STRAYS:
                self.assertTrue((repo / name).exists())
                self.assertFalse((overlay / name).exists())

    def test_stops_on_other_untracked_root_files(self):
        preflight_check = _load_preflight_check_module()
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            overlay = Path(td) / "overlay"
            repo.mkdir(parents=True, exist_ok=True)
            overlay.mkdir(parents=True, exist_ok=True)

            r = _run(["git", "init"], repo)
            self.assertEqual(r.returncode, 0, r.stderr)

            # Create a random untracked root file; should stop and not ingest.
            (repo / "random.txt").write_text("x\n", encoding="utf-8")

            env = os.environ.copy()
            env["CLAWD_GOV_OVERLAY_DIR"] = str(overlay)
            env["CLAWD_GOV_OVERLAY_SYNC"] = str(overlay / "sync_into_repo.sh")

            buf = io.StringIO()
            with redirect_stdout(buf):
                with unittest.mock.patch.dict(os.environ, env, clear=False):
                    summary = preflight_check._auto_ingest_known_gov_root_strays(repo)

            self.assertIsNotNone(summary)
            self.assertTrue(summary.get("stopped"))


if __name__ == "__main__":
    unittest.main()
