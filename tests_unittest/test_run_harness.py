import argparse
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "workspace" / "scripts" / "run_harness.py"


def load_module():
    script_dir = str(MODULE_PATH.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location("run_harness", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RunHarnessTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def _make_repo_root(self, root: Path) -> None:
        (root / "workspace" / "audit").mkdir(parents=True, exist_ok=True)
        (root / "workspace" / "state_runtime").mkdir(parents=True, exist_ok=True)
        (root / "memory").mkdir(parents=True, exist_ok=True)
        (root / "MEMORY.md").write_text("# MEMORY.md - Long-Term Context\n", encoding="utf-8")

    def _args(self, root: Path, run_id: str, checkpoints: int = 2) -> argparse.Namespace:
        return argparse.Namespace(
            run_id=run_id,
            duration_seconds=0,
            checkpoints=checkpoints,
            checkpoint_interval_seconds=1,
            accelerated=True,
            dry_run=True,
            repo_root=str(root),
        )

    def test_dry_run_creates_run_dir_and_checkpoints(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._make_repo_root(root)
            exit_code, summary = self.mod.run_harness(
                self._args(root, "dryrun_artifacts", checkpoints=2),
                env={},
            )

            self.assertEqual(exit_code, 0)
            run_dir = root / "workspace" / "state_runtime" / "runs" / "dryrun_artifacts"
            self.assertTrue(run_dir.exists())
            checkpoints = sorted((run_dir / "checkpoints").glob("checkpoint_*.json"))
            self.assertEqual(len(checkpoints), 2)
            self.assertEqual(summary["completed_checkpoints"], 2)

    def test_resolve_orchestration_limits_respects_concurrency_and_timeout_clamp(self):
        max_concurrent, timeout_seconds = self.mod.resolve_orchestration_limits(
            {
                "OPENCLAW_SUBAGENT_MAX_CONCURRENT": "7",
                "OPENCLAW_SESSIONS_SPAWN_TIMEOUT_SECONDS": "9999",
            }
        )
        self.assertEqual(max_concurrent, 7)
        self.assertEqual(timeout_seconds, 900)

    def test_stops_on_artifact_cap(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._make_repo_root(root)
            exit_code, summary = self.mod.run_harness(
                self._args(root, "artifact_cap_case", checkpoints=2),
                env={"OPENCLAW_RUN_MAX_FILES": "1"},
            )

            self.assertEqual(exit_code, 1)
            self.assertEqual(summary["status"], "failed")
            events = [event["event"] for event in summary["kill_switch_events"]]
            self.assertIn("ARTIFACT_CAP_EXCEEDED", events)

    def test_writes_final_summary_and_returns_zero_on_success(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._make_repo_root(root)
            exit_code, summary = self.mod.run_harness(
                self._args(root, "final_summary_case", checkpoints=1),
                env={},
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(summary["status"], "ok")
            final_summary_path = (
                root / "workspace" / "state_runtime" / "runs" / "final_summary_case" / "final_summary.json"
            )
            self.assertTrue(final_summary_path.exists())
            on_disk = json.loads(final_summary_path.read_text(encoding="utf-8"))
            self.assertEqual(on_disk["status"], "ok")
            self.assertEqual(on_disk["completed_checkpoints"], 1)

    def test_run_memory_step_normalizes_recent_daily_memory_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._make_repo_root(root)
            target = root / "memory" / "2026-03-09.md"
            target.write_text("# 2026-03-09\\n\\n## Updates\\n- malformed\\nentry", encoding="utf-8")

            payload = self.mod.run_memory_step(root, env={})

            self.assertIn("normalization", payload)
            self.assertEqual(payload["normalization"]["normalized_count"], 1)
            body = target.read_text(encoding="utf-8")
            self.assertIn("# Daily Memory - 2026-03-09\n", body)


class TestPureFunctions(unittest.TestCase):
    """Tests for run_harness pure/utility functions."""

    def setUp(self):
        self.mod = load_module()

    # --- utc_stamp ---

    def test_utc_stamp_returns_string(self):
        self.assertIsInstance(self.mod.utc_stamp(), str)

    def test_utc_stamp_ends_with_z(self):
        stamp = self.mod.utc_stamp()
        self.assertTrue(stamp.endswith("Z"), f"Expected Z suffix: {stamp}")

    def test_utc_stamp_format(self):
        import re
        stamp = self.mod.utc_stamp()
        self.assertRegex(stamp, r"^\d{8}T\d{6}Z$")

    # --- make_run_id ---

    def test_make_run_id_returns_string(self):
        self.assertIsInstance(self.mod.make_run_id(), str)

    def test_make_run_id_contains_prefix(self):
        run_id = self.mod.make_run_id("myprefix")
        self.assertTrue(run_id.startswith("myprefix_"))

    def test_make_run_id_default_prefix(self):
        run_id = self.mod.make_run_id()
        self.assertIn("_", run_id)

    # --- redact_env ---

    def test_redact_env_key_containing_key(self):
        self.assertEqual(self.mod.redact_env("OPENAI_API_KEY", "sk-secret"), "<redacted>")

    def test_redact_env_key_containing_token(self):
        self.assertEqual(self.mod.redact_env("AUTH_TOKEN", "mytoken"), "<redacted>")

    def test_redact_env_key_containing_secret(self):
        self.assertEqual(self.mod.redact_env("MY_SECRET", "s3cr3t"), "<redacted>")

    def test_redact_env_key_containing_pass(self):
        self.assertEqual(self.mod.redact_env("DB_PASS", "pw123"), "<redacted>")

    def test_redact_env_safe_key_passthrough(self):
        result = self.mod.redact_env("OPENCLAW_MODEL", "gpt-4")
        self.assertEqual(result, "gpt-4")

    def test_redact_env_case_insensitive(self):
        self.assertEqual(self.mod.redact_env("api_key", "val"), "<redacted>")

    # --- collect_openclaw_env ---

    def test_collect_openclaw_env_filters_prefix(self):
        env = {"OPENCLAW_MODEL": "gpt-4", "HOME": "/home/user", "OPENCLAW_TIMEOUT": "30"}
        result = self.mod.collect_openclaw_env(env)
        self.assertIn("OPENCLAW_MODEL", result)
        self.assertIn("OPENCLAW_TIMEOUT", result)
        self.assertNotIn("HOME", result)

    def test_collect_openclaw_env_redacts_keys(self):
        env = {"OPENCLAW_API_KEY": "sk-secret"}
        result = self.mod.collect_openclaw_env(env)
        self.assertEqual(result["OPENCLAW_API_KEY"], "<redacted>")

    def test_collect_openclaw_env_empty_returns_empty(self):
        result = self.mod.collect_openclaw_env({})
        self.assertEqual(result, {})

    def test_collect_openclaw_env_sorted(self):
        env = {"OPENCLAW_Z": "z", "OPENCLAW_A": "a", "OPENCLAW_M": "m"}
        result = self.mod.collect_openclaw_env(env)
        self.assertEqual(list(result.keys()), sorted(result.keys()))

    # --- exceeds_caps ---

    def test_exceeds_caps_within_limits(self):
        self.assertFalse(self.mod.exceeds_caps({"file_count": 10, "total_bytes": 100}, 100, 1000))

    def test_exceeds_caps_file_count_over(self):
        self.assertTrue(self.mod.exceeds_caps({"file_count": 101, "total_bytes": 100}, 100, 1000))

    def test_exceeds_caps_bytes_over(self):
        self.assertTrue(self.mod.exceeds_caps({"file_count": 10, "total_bytes": 1001}, 100, 1000))

    def test_exceeds_caps_exactly_at_limit(self):
        self.assertFalse(self.mod.exceeds_caps({"file_count": 100, "total_bytes": 1000}, 100, 1000))

    # --- scan_tree_usage ---

    def test_scan_tree_usage_missing_dir(self):
        result = self.mod.scan_tree_usage(Path("/nonexistent/path/xyz"))
        self.assertEqual(result, {"file_count": 0, "total_bytes": 0})

    def test_scan_tree_usage_counts_files(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / "a.txt").write_text("hello", encoding="utf-8")
            (p / "b.txt").write_text("world", encoding="utf-8")
            result = self.mod.scan_tree_usage(p)
            self.assertEqual(result["file_count"], 2)
            self.assertGreater(result["total_bytes"], 0)

    def test_scan_tree_usage_returns_dict(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.mod.scan_tree_usage(Path(td))
            self.assertIsInstance(result, dict)
            self.assertIn("file_count", result)
            self.assertIn("total_bytes", result)

    # --- append_line ---

    def test_append_line_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sub" / "log.txt"
            self.mod.append_line(p, "hello")
            self.assertTrue(p.exists())
            self.assertEqual(p.read_text(encoding="utf-8"), "hello\n")

    def test_append_line_appends_multiple(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.txt"
            self.mod.append_line(p, "first")
            self.mod.append_line(p, "second")
            lines = p.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines, ["first", "second"])

    def test_append_line_strips_trailing_newline(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.txt"
            self.mod.append_line(p, "hello\n\n")
            content = p.read_text(encoding="utf-8")
            self.assertEqual(content.count("\n"), 1)


if __name__ == "__main__":
    unittest.main()
