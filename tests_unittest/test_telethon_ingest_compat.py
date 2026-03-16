import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import telethon_ingest


class _FakeReader:
    def __init__(self):
        self.auth_calls = []
        self.run_calls = []

    async def authenticate(self, **kwargs):
        self.auth_calls.append(kwargs)

    async def run_ingestion(self, **kwargs):
        self.run_calls.append(kwargs)


class TestTelethonIngestCompat(unittest.TestCase):
    def test_run_maps_legacy_env_and_delegates_to_canonical_reader(self):
        fake_reader = _FakeReader()
        with tempfile.TemporaryDirectory() as td:
            env_file = Path(td) / "secrets.env"
            env_file.write_text("TELETHON_API_ID=12345\nTELETHON_API_HASH=hash123\n", encoding="utf-8")

            with patch.object(telethon_ingest, "DEFAULT_ENV_FILES", (env_file,)):
                with patch.object(telethon_ingest, "_load_reader_module", return_value=fake_reader):
                    with patch.dict(os.environ, {}, clear=True):
                        exit_code = telethon_ingest.run(["--once", "--backfill", "25", "--dry-run"])
                        mapped_api_id = os.environ["TG_API_ID"]
                        mapped_api_hash = os.environ["TG_API_HASH"]

        self.assertEqual(exit_code, 0)
        self.assertEqual(mapped_api_id, "12345")
        self.assertEqual(mapped_api_hash, "hash123")
        self.assertEqual(
            fake_reader.run_calls,
            [{"dry_run": True, "backfill_limit": 25, "exit_after_backfill": True, "force_prompt": False}],
        )

    def test_auth_delegates_without_running_ingestion(self):
        fake_reader = _FakeReader()
        with patch.object(telethon_ingest, "DEFAULT_ENV_FILES", ()):
            with patch.object(telethon_ingest, "_load_reader_module", return_value=fake_reader):
                with patch.dict(os.environ, {}, clear=True):
                    exit_code = telethon_ingest.run(["--auth"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(fake_reader.auth_calls, [{"force_prompt": False}])
        self.assertEqual(fake_reader.run_calls, [])

    def test_reconfigure_forwards_force_prompt(self):
        fake_reader = _FakeReader()
        with patch.object(telethon_ingest, "DEFAULT_ENV_FILES", ()):
            with patch.object(telethon_ingest, "_load_reader_module", return_value=fake_reader):
                with patch.dict(os.environ, {}, clear=True):
                    exit_code = telethon_ingest.run(["--auth", "--reconfigure"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(fake_reader.auth_calls, [{"force_prompt": True}])
        self.assertEqual(fake_reader.run_calls, [])


if __name__ == "__main__":
    unittest.main()
