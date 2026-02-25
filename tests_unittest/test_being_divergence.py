import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = REPO_ROOT / "workspace"
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from store.being_divergence import BASELINE, being_divergence, run_divergence_analysis


class TestBeingDivergence(unittest.TestCase):
    def test_deterministic_scores(self):
        corpus = {
            "c_lawd": ["governance deterministic audit"],
            "Claude Code": ["implementation patch tests"],
            "Grok": ["playful trends synthesis"],
            "ChatGPT": ["balanced practical response"],
        }
        one = being_divergence("c_lawd", "Claude Code", texts_by_being=corpus)
        two = being_divergence("c_lawd", "Claude Code", texts_by_being=corpus)
        self.assertAlmostEqual(one, two, places=8)

    def test_baseline_and_logging_flag(self):
        self.assertAlmostEqual(BASELINE, 1.0 / 7.0, places=9)
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                _ = run_divergence_analysis(enable_log=False)
                target = Path(td) / "workspace" / "state_runtime" / "store" / "being_divergence.jsonl"
                self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
