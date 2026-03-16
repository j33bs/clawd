from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.set_twitter_api_credentials import backup_file, render_env, validate_values, write_env_file


class TestSetTwitterApiCredentials(unittest.TestCase):
    def test_render_env_orders_only_present_fields(self) -> None:
        rendered = render_env(
            {
                "X_BEARER_TOKEN": "bearer",
                "X_ACCESS_TOKEN": "access",
            }
        )
        self.assertIn("X_BEARER_TOKEN=bearer", rendered)
        self.assertIn("X_ACCESS_TOKEN=access", rendered)
        self.assertNotIn("X_API_KEY=", rendered)

    def test_write_env_file_sets_permissions_and_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / "twitter_api.env"
            env_path.write_text("old\n", encoding="utf-8")

            backup = backup_file(env_path)
            self.assertIsNotNone(backup)
            self.assertEqual(backup.read_text(encoding="utf-8"), "old\n")

            write_env_file(env_path, {"X_BEARER_TOKEN": "secret"})
            self.assertEqual(env_path.read_text(encoding="utf-8").splitlines()[-1], "X_BEARER_TOKEN=secret")
            self.assertEqual(env_path.stat().st_mode & 0o777, 0o600)

    def test_validate_values_accepts_full_oauth1_without_bearer(self) -> None:
        validate_values(
            {
                "X_API_KEY": "ckey",
                "X_API_SECRET": "csecret",
                "X_ACCESS_TOKEN": "atoken",
                "X_ACCESS_TOKEN_SECRET": "asecret",
            }
        )


if __name__ == "__main__":
    unittest.main()
