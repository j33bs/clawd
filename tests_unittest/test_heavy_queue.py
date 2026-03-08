import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "workspace" / "scripts" / "heavy_queue.py"


class TestHeavyQueue(unittest.TestCase):
    def test_enqueue_outputs_deterministic_job(self):
        with tempfile.TemporaryDirectory() as td:
            env = dict(os.environ)
            env["OPENCLAW_HEAVY_QUEUE_PATH"] = str(Path(td) / "heavy_jobs.jsonl")
            run = subprocess.run(
                [sys.executable, str(SCRIPT), "enqueue", "--cmd", "echo hello"],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            payload = json.loads(run.stdout)
            self.assertEqual(payload["state"], "queued")
            self.assertEqual(payload["cmd"], "echo hello")
            self.assertEqual(payload["schema"], 1)


class TestHeavyQueuePure(unittest.TestCase):
    """Unit tests for heavy_queue pure functions — enqueue structure, tail_jobs."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("heavy_queue", SCRIPT)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_queue = self.mod.QUEUE_PATH
        self.mod.QUEUE_PATH = Path(self._tmpdir.name) / "heavy_jobs.jsonl"

    def tearDown(self):
        self.mod.QUEUE_PATH = self._original_queue
        self._tmpdir.cleanup()

    # --- utc_stamp ---

    def test_utc_stamp_returns_string(self):
        result = self.mod.utc_stamp()
        self.assertIsInstance(result, str)

    def test_utc_stamp_ends_with_z(self):
        result = self.mod.utc_stamp()
        self.assertTrue(result.endswith("Z"))

    def test_utc_stamp_no_microseconds(self):
        result = self.mod.utc_stamp()
        self.assertNotIn(".", result)

    # --- enqueue ---

    def test_enqueue_returns_dict(self):
        result = self.mod.enqueue(cmd="echo hello", kind="codegen", priority=5, ttl_minutes=30)
        self.assertIsInstance(result, dict)

    def test_enqueue_state_queued(self):
        result = self.mod.enqueue(cmd="echo hi", kind="codegen", priority=5, ttl_minutes=10)
        self.assertEqual(result["state"], "queued")

    def test_enqueue_schema_is_1(self):
        result = self.mod.enqueue(cmd="echo hi", kind="codegen", priority=5, ttl_minutes=10)
        self.assertEqual(result["schema"], 1)

    def test_enqueue_cmd_preserved(self):
        result = self.mod.enqueue(cmd="python my_script.py", kind="codegen", priority=5, ttl_minutes=10)
        self.assertEqual(result["cmd"], "python my_script.py")

    def test_enqueue_id_is_uuid(self):
        import uuid
        result = self.mod.enqueue(cmd="cmd", kind="kind", priority=1, ttl_minutes=1)
        self.assertIsNotNone(uuid.UUID(result["id"]))

    def test_enqueue_has_ts_field(self):
        result = self.mod.enqueue(cmd="cmd", kind="kind", priority=1, ttl_minutes=1)
        self.assertIn("ts", result)
        self.assertTrue(result["ts"].endswith("Z"))

    def test_enqueue_has_expires_at(self):
        result = self.mod.enqueue(cmd="cmd", kind="kind", priority=1, ttl_minutes=60)
        self.assertIn("expires_at", result)
        self.assertTrue(result["expires_at"].endswith("Z"))

    def test_enqueue_requires_gpu_false_by_default(self):
        result = self.mod.enqueue(cmd="cmd", kind="kind", priority=1, ttl_minutes=1)
        self.assertFalse(result["requires_gpu"])

    def test_enqueue_requires_gpu_sets_tool_id(self):
        result = self.mod.enqueue(cmd="cmd", kind="kind", priority=1, ttl_minutes=1, requires_gpu=True)
        self.assertTrue(result["requires_gpu"])
        self.assertIsNotNone(result["tool_id"])

    def test_enqueue_writes_to_queue(self):
        self.mod.enqueue(cmd="cmd", kind="kind", priority=1, ttl_minutes=1)
        self.assertTrue(self.mod.QUEUE_PATH.exists())

    def test_enqueue_meta_preserved(self):
        result = self.mod.enqueue(cmd="cmd", kind="kind", priority=1, ttl_minutes=1, meta={"ref": "test"})
        self.assertEqual(result["meta"]["ref"], "test")

    # --- tail_jobs ---

    def test_tail_jobs_missing_returns_empty(self):
        result = self.mod.tail_jobs(10)
        self.assertEqual(result, [])

    def test_tail_jobs_returns_enqueued(self):
        self.mod.enqueue(cmd="cmd1", kind="k", priority=1, ttl_minutes=1)
        self.mod.enqueue(cmd="cmd2", kind="k", priority=1, ttl_minutes=1)
        result = self.mod.tail_jobs(10)
        self.assertEqual(len(result), 2)

    def test_tail_jobs_limit_respected(self):
        for i in range(5):
            self.mod.enqueue(cmd=f"cmd{i}", kind="k", priority=1, ttl_minutes=1)
        result = self.mod.tail_jobs(3)
        self.assertLessEqual(len(result), 3)

    def test_tail_jobs_skips_invalid_json(self):
        self.mod.enqueue(cmd="valid", kind="k", priority=1, ttl_minutes=1)
        # Append corrupt line
        with self.mod.QUEUE_PATH.open("a") as f:
            f.write("not valid json\n")
        result = self.mod.tail_jobs(10)
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
