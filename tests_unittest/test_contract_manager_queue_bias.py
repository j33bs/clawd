import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def load_module():
    root = Path(__file__).resolve().parents[1]
    mod_path = root / "workspace" / "scripts" / "contract_manager.py"
    spec = importlib.util.spec_from_file_location("contract_manager_test_mod", mod_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class TestContractManagerQueueBias(unittest.TestCase):
    def test_queue_depth_counts_queued_non_expired_minus_done(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            queue = base / "heavy_jobs.jsonl"
            runs = base / "heavy_runs.jsonl"

            queue.write_text(
                "\n".join(
                    [
                        json.dumps({"id": "a", "state": "queued", "expires_at": "2999-01-01T00:00:00Z", "cmd": "echo a"}),
                        json.dumps({"id": "b", "state": "queued", "expires_at": "2000-01-01T00:00:00Z", "cmd": "echo b"}),
                        json.dumps({"id": "c", "state": "queued", "expires_at": "2999-01-01T00:00:00Z", "cmd": "echo c"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            runs.write_text(json.dumps({"job_id": "c", "status": "ok"}) + "\n", encoding="utf-8")

            self.assertEqual(mod.queue_depth(str(queue), str(runs)), 1)

    def test_should_transition_uses_backlog_bias_only_when_idle_and_low(self):
        mod = load_module()
        policy = {
            "min_mode_minutes": 0,
            "service_rate_high": 0.30,
            "service_rate_low": 0.08,
        }
        cur = {
            "mode": "SERVICE",
            "service_load": {"ewma_rate": 0.05},
            "last_transition": {"ts": "2000-01-01T00:00:00Z"},
        }
        load = {"idle": True, "rate_per_min": 0.0}

        tr = mod.should_transition(cur, policy, load, queue_depth_now=2, service_override_active=False)
        self.assertIsNotNone(tr)
        self.assertEqual(tr["to"], "CODE")
        self.assertIn("queue_depth", tr["reason"])

        tr2 = mod.should_transition(cur, policy, load, queue_depth_now=2, service_override_active=True)
        self.assertIsNone(tr2)

        cur_high = {
            "mode": "SERVICE",
            "service_load": {"ewma_rate": 0.2},
            "last_transition": {"ts": "2000-01-01T00:00:00Z"},
        }
        tr3 = mod.should_transition(cur_high, policy, load, queue_depth_now=5, service_override_active=False)
        self.assertIsNone(tr3)

    def test_queue_depth_uses_latest_state_from_append_only_queue(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            queue = base / "heavy_jobs.jsonl"
            runs = base / "heavy_runs.jsonl"
            runs.write_text("", encoding="utf-8")
            queue.write_text(
                "\n".join(
                    [
                        json.dumps({"id": "x1", "state": "queued", "expires_at": "2999-01-01T00:00:00Z", "cmd": "echo x"}),
                        json.dumps({"id": "x1", "state": "running", "ts": "2026-03-02T00:00:00Z"}),
                        json.dumps({"id": "x1", "state": "done", "rc": 0, "ts": "2026-03-02T00:00:01Z"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(mod.queue_depth(str(queue), str(runs)), 0)


if __name__ == "__main__":
    unittest.main()
