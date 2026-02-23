import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "workspace" / "scripts" / "analyze_inquiry_momentum.py"
    spec = importlib.util.spec_from_file_location("analyze_inquiry_momentum_module", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestAnalyzeInquiryMomentum(unittest.TestCase):
    def test_grouped_aggregates(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "wander_log.jsonl"
            rows = [
                {"trigger": "cron", "inquiry_momentum_score": 0.8, "exceeded": True},
                {"trigger": "cron", "inquiry_momentum_score": 0.6, "exceeded": False},
                {"trigger": "task", "inquiry_momentum_score": 0.4, "exceeded": False},
                {"inquiry_momentum_score": 0.9, "exceeded": True},
            ]
            log_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            summary = module.summarize(module.load_rows(log_path))
            self.assertEqual(summary["total_rows"], 4)
            self.assertIn("cron", summary["triggers"])
            self.assertEqual(summary["triggers"]["cron"]["n"], 2)
            self.assertAlmostEqual(summary["triggers"]["cron"]["mean"], 0.7, places=6)
            self.assertIn("unknown", summary["triggers"])


if __name__ == "__main__":
    unittest.main()

