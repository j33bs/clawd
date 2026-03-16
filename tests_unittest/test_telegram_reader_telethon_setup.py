import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workspace.itc_pipeline import telegram_reader_telethon as reader


class TestTelegramReaderTelethonSetup(unittest.TestCase):
    def test_resolve_config_prompts_and_persists_when_missing(self):
        with tempfile.TemporaryDirectory() as td:
            env_path = Path(td) / "secrets.env"
            with patch.dict(os.environ, {}, clear=True):
                with patch.object(reader, "DEFAULT_SECRETS_ENV_PATH", env_path):
                    with patch.object(reader, "_interactive_available", return_value=True):
                        with patch("builtins.input", side_effect=["12345", "+61123456789", "", "y"]):
                            with patch("getpass.getpass", return_value="hash123"):
                                with patch.object(reader, "_persist_runtime_config") as persist:
                                    config = reader.resolve_config(prompt_if_missing=True, require_phone=True)

        self.assertEqual(config["api_id"], "12345")
        self.assertEqual(config["api_hash"], "hash123")
        self.assertEqual(config["phone"], "+61123456789")
        self.assertTrue(config["session_path"].endswith("/.secrets/telethon_itc.session"))
        persist.assert_called_once_with(config)

    def test_resolve_config_uses_existing_env_without_prompt(self):
        env = {
            "TG_API_ID": "111",
            "TG_API_HASH": "hash111",
            "TG_PHONE": "+61000",
            "TG_SESSION_PATH": "/tmp/telethon.session",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("builtins.input") as prompt:
                with patch("getpass.getpass") as secret_prompt:
                    config = reader.resolve_config(prompt_if_missing=True, require_phone=True)

        self.assertEqual(config["api_id"], "111")
        self.assertEqual(config["api_hash"], "hash111")
        self.assertEqual(config["phone"], "+61000")
        self.assertEqual(config["session_path"], "/tmp/telethon.session")
        prompt.assert_not_called()
        secret_prompt.assert_not_called()

    def test_resolve_config_reconfigure_prompts_for_existing_values(self):
        env = {
            "TG_API_ID": "111",
            "TG_API_HASH": "oldhash",
            "TG_PHONE": "+61000",
            "TG_SESSION_PATH": "/tmp/telethon.session",
        }
        with tempfile.TemporaryDirectory() as td:
            env_path = Path(td) / "secrets.env"
            with patch.dict(os.environ, env, clear=True):
                with patch.object(reader, "DEFAULT_SECRETS_ENV_PATH", env_path):
                    with patch.object(reader, "_interactive_available", return_value=True):
                        with patch("builtins.input", side_effect=["", "", "", "y"]):
                            with patch("getpass.getpass", return_value="newhash"):
                                with patch.object(reader, "_persist_runtime_config") as persist:
                                    config = reader.resolve_config(
                                        prompt_if_missing=True,
                                        require_phone=True,
                                        force_prompt=True,
                                    )

        self.assertEqual(config["api_id"], "111")
        self.assertEqual(config["api_hash"], "newhash")
        self.assertEqual(config["phone"], "+61000")
        self.assertEqual(config["session_path"], "/tmp/telethon.session")
        persist.assert_called_once_with(config)


if __name__ == "__main__":
    unittest.main()
