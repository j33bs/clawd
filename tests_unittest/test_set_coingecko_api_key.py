import tempfile
import unittest
from pathlib import Path

from workspace.scripts.set_coingecko_api_key import _update_market_config, _update_openclaw_env


class TestSetCoinGeckoApiKey(unittest.TestCase):
    def test_update_openclaw_env_writes_key(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "openclaw.json"
            cfg.write_text('{"env":{"vars":{"OPENCLAW_HOME":"/tmp/clawd"}}}\n', encoding="utf-8")
            backup = _update_openclaw_env(cfg, "demo-key")
            self.assertTrue(backup.is_file())
            self.assertIn('"COINGECKO_API_KEY": "demo-key"', cfg.read_text(encoding="utf-8"))

    def test_update_market_config_can_switch_to_pro(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "market_sentiment_sources.json"
            cfg.write_text(
                '{"sources":{"coingecko":{"base_url":"https://api.coingecko.com/api/v3"}}}\n',
                encoding="utf-8",
            )
            backup, base_url = _update_market_config(cfg, mode="pro")
            self.assertTrue(backup.is_file())
            self.assertEqual(base_url, "https://pro-api.coingecko.com/api/v3")
            text = cfg.read_text(encoding="utf-8")
            self.assertIn('"api_key_env": "COINGECKO_API_KEY"', text)
            self.assertIn('"base_url": "https://pro-api.coingecko.com/api/v3"', text)


if __name__ == "__main__":
    unittest.main()
