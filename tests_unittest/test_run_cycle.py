import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import run_cycle  # noqa: E402


class RunCycleTests(unittest.TestCase):
    def test_run_invokes_market_classify_and_sim_in_order(self):
        calls = []

        with patch.object(run_cycle.market_stream, "run", side_effect=lambda **kwargs: calls.append(("market", kwargs))):
            with patch.object(run_cycle.itc_classify, "run", side_effect=lambda **kwargs: calls.append(("classify", kwargs))):
                with patch.object(run_cycle.sim_runner, "run", side_effect=lambda **kwargs: calls.append(("sim", kwargs))):
                    out = run_cycle.run(
                        config_path="pipelines/system1_trading.yaml",
                        features_path="pipelines/system1_trading.features.yaml",
                        full=True,
                        market_limit=123,
                        max_llm=9,
                        model="local-assistant",
                        rules_only=False,
                        sim_id="SIM_A",
                        symbols=["BTCUSDT"],
                    )

        self.assertEqual(out, 0)
        self.assertEqual([name for name, _ in calls], ["market", "classify", "sim"])
        self.assertEqual(calls[0][1]["limit"], 123)
        self.assertEqual(calls[1][1]["max_llm"], 9)
        self.assertEqual(calls[2][1]["sim_filter"], "SIM_A")

    def test_run_can_skip_market_stage(self):
        calls = []

        with patch.object(run_cycle.market_stream, "run", side_effect=lambda **kwargs: calls.append(("market", kwargs))):
            with patch.object(run_cycle.itc_classify, "run", side_effect=lambda **kwargs: calls.append(("classify", kwargs))):
                with patch.object(run_cycle.sim_runner, "run", side_effect=lambda **kwargs: calls.append(("sim", kwargs))):
                    out = run_cycle.run(
                        config_path="pipelines/system1_trading.yaml",
                        features_path="pipelines/system1_trading.features.yaml",
                        skip_market=True,
                    )

        self.assertEqual(out, 0)
        self.assertEqual([name for name, _ in calls], ["classify", "sim"])


if __name__ == "__main__":
    unittest.main()
