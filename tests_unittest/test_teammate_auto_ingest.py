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


class TestTeammateAutoIngest(unittest.TestCase):
    def test_governance_docs_plus_allowlisted_file_commits_when_gates_skipped(self):
        preflight_check = _load_preflight_check_module()
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            overlay = Path(td) / "overlay"
            repo.mkdir(parents=True, exist_ok=True)
            overlay.mkdir(parents=True, exist_ok=True)
            _init_repo(repo)

            # Untracked governance docs at repo root (Stage A should ingest them).
            for name in preflight_check._KNOWN_GOV_ROOT_STRAYS:
                (repo / name).write_text(f"dummy {name}\n", encoding="utf-8")

            # Allowlisted teammate file (Stage B should ingest it).
            (repo / "core" / "integration").mkdir(parents=True, exist_ok=True)
            econ = repo / "core" / "integration" / "econ_adapter.js"
            econ.write_text("export function econ() { return 1; }\n", encoding="utf-8")

            sync = _write_sync_script(overlay)

            env = os.environ.copy()
            env["CLAWD_GOV_OVERLAY_DIR"] = str(overlay)
            env["CLAWD_GOV_OVERLAY_SYNC"] = str(sync)
            env["CLAWD_PREFLIGHT_SKIP_UNITTESTS"] = "1"
            env["CLAWD_PREFLIGHT_SKIP_NPM_TESTS"] = "1"

            with unittest.mock.patch.dict(os.environ, env, clear=False):
                s1 = preflight_check._auto_ingest_known_gov_root_strays(repo)
                self.assertIsNotNone(s1)
                self.assertFalse(s1.get("stopped"))

                buf = io.StringIO()
                with redirect_stdout(buf):
                    s2 = preflight_check._auto_ingest_allowlisted_teammate_untracked(repo)

            self.assertIsNotNone(s2)
            self.assertFalse(s2.get("stopped"))
            self.assertTrue((overlay / ".sync_ran").exists())

            # File should be committed and tracked.
            r = _run(["git", "rev-parse", "--verify", "HEAD"], repo)
            self.assertEqual(r.returncode, 0, r.stderr)
            r = _run(["git", "ls-files", "--", "core/integration/econ_adapter.js"], repo)
            self.assertIn("core/integration/econ_adapter.js", r.stdout)

    def test_governance_docs_plus_non_allowlisted_path_stops(self):
        preflight_check = _load_preflight_check_module()
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            overlay = Path(td) / "overlay"
            repo.mkdir(parents=True, exist_ok=True)
            overlay.mkdir(parents=True, exist_ok=True)
            _init_repo(repo)

            for name in preflight_check._KNOWN_GOV_ROOT_STRAYS:
                (repo / name).write_text(f"dummy {name}\n", encoding="utf-8")

            (repo / "core" / "integration").mkdir(parents=True, exist_ok=True)
            (repo / "core" / "integration" / "econ_adapter.js").write_text("x\n", encoding="utf-8")

            (repo / "core" / "other").mkdir(parents=True, exist_ok=True)
            (repo / "core" / "other" / "place.js").write_text("x\n", encoding="utf-8")

            sync = _write_sync_script(overlay)
            env = os.environ.copy()
            env["CLAWD_GOV_OVERLAY_DIR"] = str(overlay)
            env["CLAWD_GOV_OVERLAY_SYNC"] = str(sync)
            env["CLAWD_PREFLIGHT_SKIP_UNITTESTS"] = "1"
            env["CLAWD_PREFLIGHT_SKIP_NPM_TESTS"] = "1"

            with unittest.mock.patch.dict(os.environ, env, clear=False):
                s1 = preflight_check._auto_ingest_known_gov_root_strays(repo)
                self.assertIsNotNone(s1)
                self.assertFalse(s1.get("stopped"))

                s2 = preflight_check._auto_ingest_allowlisted_teammate_untracked(repo)

            self.assertIsNotNone(s2)
            self.assertTrue(s2.get("stopped"))
            self.assertEqual(s2.get("error"), "untracked_disallowed")

            # Should not have created an ingest branch.
            r = _run(["git", "branch", "--list", "teammate/ingest-*"], repo)
            self.assertEqual(r.stdout.strip(), "")

            # Allowlisted file should still be present.
            self.assertTrue((repo / "core" / "integration" / "econ_adapter.js").exists())

    def test_governance_docs_plus_wrong_extension_under_core_integration_stops(self):
        preflight_check = _load_preflight_check_module()
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            overlay = Path(td) / "overlay"
            repo.mkdir(parents=True, exist_ok=True)
            overlay.mkdir(parents=True, exist_ok=True)
            _init_repo(repo)

            for name in preflight_check._KNOWN_GOV_ROOT_STRAYS:
                (repo / name).write_text(f"dummy {name}\n", encoding="utf-8")

            (repo / "core" / "integration").mkdir(parents=True, exist_ok=True)
            (repo / "core" / "integration" / "econ_adapter.js").write_text("x\n", encoding="utf-8")
            (repo / "core" / "integration" / "other.bin").write_bytes(b"BIN")

            sync = _write_sync_script(overlay)
            env = os.environ.copy()
            env["CLAWD_GOV_OVERLAY_DIR"] = str(overlay)
            env["CLAWD_GOV_OVERLAY_SYNC"] = str(sync)

            with unittest.mock.patch.dict(os.environ, env, clear=False):
                s1 = preflight_check._auto_ingest_known_gov_root_strays(repo)
                self.assertIsNotNone(s1)
                self.assertFalse(s1.get("stopped"))

                s2 = preflight_check._auto_ingest_allowlisted_teammate_untracked(repo)

            self.assertIsNotNone(s2)
            self.assertTrue(s2.get("stopped"))
            self.assertEqual(s2.get("error"), "untracked_disallowed")

    def test_token_like_scan_quarantines_and_stops(self):
        preflight_check = _load_preflight_check_module()
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            overlay = Path(td) / "overlay"
            quarantine = Path(td) / "quarantine"
            repo.mkdir(parents=True, exist_ok=True)
            overlay.mkdir(parents=True, exist_ok=True)
            quarantine.mkdir(parents=True, exist_ok=True)
            _init_repo(repo)

            for name in preflight_check._KNOWN_GOV_ROOT_STRAYS:
                (repo / name).write_text(f"dummy {name}\n", encoding="utf-8")

            (repo / "core" / "integration").mkdir(parents=True, exist_ok=True)
            econ = repo / "core" / "integration" / "econ_adapter.js"
            econ.write_text("export const x = 1;\n", encoding="utf-8")

            sync = _write_sync_script(overlay)
            env = os.environ.copy()
            env["CLAWD_GOV_OVERLAY_DIR"] = str(overlay)
            env["CLAWD_GOV_OVERLAY_SYNC"] = str(sync)
            env["CLAWD_PREFLIGHT_QUARANTINE_DIR"] = str(quarantine)

            with unittest.mock.patch.dict(os.environ, env, clear=False):
                s1 = preflight_check._auto_ingest_known_gov_root_strays(repo)
                self.assertIsNotNone(s1)
                self.assertFalse(s1.get("stopped"))

                with unittest.mock.patch.object(preflight_check, "_scan_token_like", return_value=["rule_test"]):
                    s2 = preflight_check._auto_ingest_allowlisted_teammate_untracked(repo)

            self.assertIsNotNone(s2)
            self.assertTrue(s2.get("stopped"))
            self.assertEqual(s2.get("error"), "safety_scan_failed")

            # The allowlisted file should have been moved to the quarantine dir.
            qroot = Path(s2["quarantine"]["quarantine_root"])
            self.assertTrue((qroot / "core" / "integration" / "econ_adapter.js").exists())
            self.assertFalse((repo / "core" / "integration" / "econ_adapter.js").exists())

    def test_symlink_or_dir_under_allowlist_stops_no_quarantine(self):
        preflight_check = _load_preflight_check_module()
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            overlay = Path(td) / "overlay"
            quarantine = Path(td) / "quarantine"
            repo.mkdir(parents=True, exist_ok=True)
            overlay.mkdir(parents=True, exist_ok=True)
            quarantine.mkdir(parents=True, exist_ok=True)
            _init_repo(repo)

            for name in preflight_check._KNOWN_GOV_ROOT_STRAYS:
                (repo / name).write_text(f"dummy {name}\n", encoding="utf-8")

            (repo / "core" / "integration").mkdir(parents=True, exist_ok=True)
            bad = repo / "core" / "integration" / "econ_adapter.js"

            # Prefer a symlink; fall back to directory if symlinks are unavailable.
            made_symlink = False
            if hasattr(os, "symlink"):
                target = repo / "core" / "integration" / "_target.txt"
                target.write_text("x\n", encoding="utf-8")
                # Make the symlink target tracked so it doesn't appear as untracked drift.
                r = _run(["git", "add", "--", "core/integration/_target.txt"], repo)
                self.assertEqual(r.returncode, 0, r.stderr)
                r = _run(["git", "commit", "-m", "test: seed tracked target"], repo)
                self.assertEqual(r.returncode, 0, r.stderr)
                try:
                    os.symlink(str(target), str(bad))
                    made_symlink = True
                except OSError:
                    made_symlink = False
            if not made_symlink:
                bad.mkdir(parents=True, exist_ok=True)

            sync = _write_sync_script(overlay)
            env = os.environ.copy()
            env["CLAWD_GOV_OVERLAY_DIR"] = str(overlay)
            env["CLAWD_GOV_OVERLAY_SYNC"] = str(sync)
            env["CLAWD_PREFLIGHT_QUARANTINE_DIR"] = str(quarantine)

            with unittest.mock.patch.dict(os.environ, env, clear=False):
                s1 = preflight_check._auto_ingest_known_gov_root_strays(repo)
                self.assertIsNotNone(s1)
                self.assertFalse(s1.get("stopped"))

                s2 = preflight_check._auto_ingest_allowlisted_teammate_untracked(repo)

            self.assertIsNotNone(s2)
            self.assertTrue(s2.get("stopped"))
            self.assertEqual(s2.get("error"), "non_regular_file")

            # Ensure nothing got moved into quarantine (fail-fast, no partial moves).
            self.assertEqual(list(quarantine.glob("openclaw-quarantine-*")), [])


if __name__ == "__main__":
    unittest.main()
