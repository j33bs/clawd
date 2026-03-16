import tempfile
import unittest
from pathlib import Path

from workspace.scripts.set_coinmarketcap_api_key import _update_market_config, _update_openclaw_env


class TestSetCoinMarketCapApiKey(unittest.TestCase):
    def test_update_openclaw_env_writes_key(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "openclaw.json"
            cfg.write_text('{"env":{"vars":{"OPENCLAW_HOME":"/tmp/clawd"}}}\n', encoding="utf-8")
            backup = _update_openclaw_env(cfg, "cmc-key")
            self.assertTrue(backup.is_file())
            self.assertIn('"COINMARKETCAP_API_KEY": "cmc-key"', cfg.read_text(encoding="utf-8"))

    def test_update_market_config_sets_env_binding(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "market_sentiment_sources.json"
            cfg.write_text(
                '{"sources":{"coinmarketcap":{"base_url":"https://old.example","api_key_env":"OLD"}}}\n',
                encoding="utf-8",
            )
            backup, base_url = _update_market_config(cfg)
            self.assertTrue(backup.is_file())
            self.assertEqual(base_url, "https://pro-api.coinmarketcap.com")
            text = cfg.read_text(encoding="utf-8")
            self.assertIn('"api_key_env": "COINMARKETCAP_API_KEY"', text)
            self.assertIn('"base_url": "https://pro-api.coinmarketcap.com"', text)


if __name__ == "__main__":
    unittest.main()
