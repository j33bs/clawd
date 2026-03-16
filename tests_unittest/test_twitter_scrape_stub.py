from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.twitter_scrape_stub import (
    build_oauth1_authorization_header,
    fetch_user_by_username_with_bearer,
    fetch_user_by_username_with_oauth1,
    load_env_file,
    resolve_auth_mode,
)


class _FakeResponse:
    def __init__(self, body: dict[str, object], status: int = 200) -> None:
        self.status_code = status
        self._json = body
        self.text = json.dumps(body)

    def json(self) -> dict[str, object]:
        return self._json

    def raise_for_status(self) -> None:
        return None


class TestTwitterScrapeStub(unittest.TestCase):
    def test_load_env_file_ignores_comments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / "twitter_api.env"
            env_path.write_text("# comment\nX_BEARER_TOKEN=abc\n\nX_API_KEY=key\n", encoding="utf-8")
            loaded = load_env_file(env_path)
            self.assertEqual(loaded["X_BEARER_TOKEN"], "abc")
            self.assertEqual(loaded["X_API_KEY"], "key")

    def test_fetch_user_by_username_with_bearer_uses_header(self) -> None:
        with patch("scripts.twitter_scrape_stub.requests.get", return_value=_FakeResponse({"data": {"id": "1", "name": "X"}})) as mocked:
            result = fetch_user_by_username_with_bearer(
                bearer_token="secret-token",
                username="x",
                base_url="https://api.x.com/2",
                timeout=5,
            )
        self.assertEqual(mocked.call_args.kwargs["headers"]["Authorization"], "Bearer secret-token")
        self.assertEqual(result["json"]["data"]["id"], "1")

    def test_build_oauth1_authorization_header_contains_expected_fields(self) -> None:
        header = build_oauth1_authorization_header(
            method="GET",
            url="https://api.x.com/2/users/by/username/x",
            consumer_key="ckey",
            consumer_secret="csecret",
            access_token="atoken",
            access_token_secret="asecret",
            nonce="nonce123",
            timestamp="1700000000",
        )
        self.assertIn('oauth_consumer_key="ckey"', header)
        self.assertIn('oauth_token="atoken"', header)
        self.assertIn('oauth_signature="', header)

    def test_fetch_user_by_username_with_oauth1_uses_oauth_header(self) -> None:
        with patch("scripts.twitter_scrape_stub.requests.get", return_value=_FakeResponse({"data": {"id": "1", "name": "X"}})) as mocked:
            fetch_user_by_username_with_oauth1(
                consumer_key="ckey",
                consumer_secret="csecret",
                access_token="atoken",
                access_token_secret="asecret",
                username="x",
                base_url="https://api.x.com/2",
                timeout=5,
            )
        auth_header = mocked.call_args.kwargs["headers"]["Authorization"]
        self.assertTrue(auth_header.startswith("OAuth "))

    def test_resolve_auth_mode_prefers_oauth1_when_complete(self) -> None:
        mode = resolve_auth_mode(
            {
                "X_API_KEY": "ckey",
                "X_API_SECRET": "csecret",
                "X_ACCESS_TOKEN": "atoken",
                "X_ACCESS_TOKEN_SECRET": "asecret",
                "X_BEARER_TOKEN": "bearer",
            },
            "auto",
        )
        self.assertEqual(mode, "oauth1")


if __name__ == "__main__":
    unittest.main()
