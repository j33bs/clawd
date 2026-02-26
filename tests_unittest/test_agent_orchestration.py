import json
import tempfile
import unittest
from pathlib import Path
import importlib.util
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "workspace" / "scripts" / "agent_orchestration.py"


def load_module():
    spec = importlib.util.spec_from_file_location("agent_orchestration", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AgentOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def test_timeout_defaults_and_clamping(self):
        with tempfile.TemporaryDirectory() as td:
            orch = self.mod.AgentOrchestrator(Path(td), timeout_default=120, max_concurrent=2)
            self.assertEqual(orch.resolve_timeout_seconds(), 120)
            self.assertEqual(orch.resolve_timeout_seconds(5), 15)
            self.assertEqual(orch.resolve_timeout_seconds(1200), 900)

    def test_handoff_acknowledgment_persists(self):
        with tempfile.TemporaryDirectory() as td:
            state_dir = Path(td)
            orch = self.mod.AgentOrchestrator(state_dir)
            handoff_id = orch.create_handoff("planner", "coder", "handoff test", {"key": "value"})
            self.assertEqual(orch.get_handoff_status(handoff_id)["status"], "pending")
            orch.acknowledge_handoff(handoff_id, "coder", "accepted")

            reloaded = self.mod.AgentOrchestrator(state_dir)
            status = reloaded.get_handoff_status(handoff_id)
            self.assertEqual(status["status"], "acknowledged")
            self.assertEqual(status["acknowledged_by"], "coder")

    def test_agent_state_persists_across_instances(self):
        with tempfile.TemporaryDirectory() as td:
            state_dir = Path(td)
            orch = self.mod.AgentOrchestrator(state_dir)
            orch.set_agent_state("main", {"mood": "focused", "state": "active"})

            reloaded = self.mod.AgentOrchestrator(state_dir)
            state = reloaded.get_agent_state("main")
            self.assertEqual(state["mood"], "focused")
            self.assertEqual(state["state"], "active")

    def test_specialization_tags_and_load_balancing(self):
        with tempfile.TemporaryDirectory() as td:
            orch = self.mod.AgentOrchestrator(Path(td))
            tags = self.mod.resolve_specialization_tags("please refactor failing test")
            self.assertIn("coding", tags)

            run_id = orch.register_run_start("main", "provider-a")
            selected = orch.select_provider(["provider-a", "provider-b"])
            self.assertEqual(selected, "provider-b")
            orch.register_run_end(run_id)

    def test_priority_queue_orders_high_then_normal_then_low(self):
        with tempfile.TemporaryDirectory() as td:
            orch = self.mod.AgentOrchestrator(Path(td))
            orch.enqueue_spawn_request({"task": "low"}, priority="low")
            orch.enqueue_spawn_request({"task": "high"}, priority="high")
            orch.enqueue_spawn_request({"task": "normal"}, priority="normal")

            self.assertEqual(orch.dequeue_spawn_request()["task"], "high")
            self.assertEqual(orch.dequeue_spawn_request()["task"], "normal")
            self.assertEqual(orch.dequeue_spawn_request()["task"], "low")

    def test_prepare_spawn_enqueues_when_concurrency_full(self):
        with tempfile.TemporaryDirectory() as td:
            orch = self.mod.AgentOrchestrator(Path(td), max_concurrent=1)
            run_id = orch.register_run_start("main", "provider-a")
            planned = orch.prepare_spawn(
                "research options",
                providers=["provider-a", "provider-b"],
                priority="high",
            )
            self.assertTrue(planned["queued"])
            self.assertEqual(planned["queue_depth"], 1)
            orch.register_run_end(run_id)

    def test_graceful_shutdown_and_resource_usage_log(self):
        with tempfile.TemporaryDirectory() as td:
            state_dir = Path(td)
            orch = self.mod.AgentOrchestrator(state_dir)
            run_id = orch.register_run_start("main", "provider-a")
            ended = orch.register_run_end(run_id, status="ok", state_update={"mood": "calm"})
            self.assertTrue(ended["ended"])
            self.assertGreaterEqual(ended["duration_ms"], 0)

            usage_lines = (state_dir / "resource_usage.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(usage_lines), 1)
            usage = json.loads(usage_lines[0])
            self.assertEqual(usage["run_id"], run_id)

            shutdown = orch.graceful_shutdown("test")
            self.assertEqual(shutdown["reason"], "test")
            state = json.loads((state_dir / "state.json").read_text(encoding="utf-8"))
            self.assertIn("shutdown", state)


if __name__ == "__main__":
    unittest.main()
