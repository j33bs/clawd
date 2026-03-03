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


if __name__ == "__main__":
    unittest.main()
