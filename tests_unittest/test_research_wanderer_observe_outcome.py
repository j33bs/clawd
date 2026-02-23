import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "workspace" / "scripts" / "research_wanderer.py"
    spec = importlib.util.spec_from_file_location("research_wanderer_module", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestResearchWandererObserveOutcome(unittest.TestCase):
    def test_called_once_and_deduped_by_session_id(self):
        module = _load_module()

        calls = []

        class _PipelineStub:
            def observe_outcome(self, **kwargs):
                calls.append(dict(kwargs))

        with tempfile.TemporaryDirectory() as td:
            observed_path = Path(td) / "observed.jsonl"
            first = module.observe_wander_outcome(
                session_id="sess-42",
                trail_ids=["t-1", "t-2"],
                trigger="cron",
                inquiry_momentum_score=0.88,
                duration_ms=32,
                context_text="question one question two",
                observed_path=observed_path,
                pipeline_factory=lambda: _PipelineStub(),
            )
            second = module.observe_wander_outcome(
                session_id="sess-42",
                trail_ids=["t-1", "t-2"],
                trigger="cron",
                inquiry_momentum_score=0.88,
                duration_ms=32,
                context_text="question one question two",
                observed_path=observed_path,
                pipeline_factory=lambda: _PipelineStub(),
            )

        self.assertTrue(first["called"])
        self.assertEqual(first["reason"], "recorded")
        self.assertFalse(second["called"])
        self.assertEqual(second["reason"], "duplicate_session")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["path"], ["wander", "codex"])
        self.assertEqual(calls[0]["source_agent"], "wander")


if __name__ == "__main__":
    unittest.main()
