import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.telegram_interface import (
    TelegramCommandInterface,
    TelegramPollerLockError,
    TelegramWebhookConflictError,
)


class _FakeHTTPResponse:
    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestTelegramInterface(unittest.TestCase):
    def test_single_instance_lock_rejects_second_poller(self):
        with tempfile.TemporaryDirectory() as td:
            lock_path = Path(td) / "telegram.lock"
            first = TelegramCommandInterface(token="x", lock_path=lock_path)
            second = TelegramCommandInterface(token="x", lock_path=lock_path)
            first._acquire_poller_lock()
            try:
                with self.assertRaises(TelegramPollerLockError):
                    second._acquire_poller_lock()
            finally:
                first._release_poller_lock()

    def test_get_webhook_info_parses_payload_via_http_mock(self):
        interface = TelegramCommandInterface(token="x")
        payload = {
            "ok": True,
            "result": {
                "url": "https://example.com/hook",
                "pending_update_count": 2,
            },
        }
        with mock.patch("cathedral.telegram_interface.urllib.request.urlopen", return_value=_FakeHTTPResponse(payload)):
            out = interface._api_get_json("getWebhookInfo", request_timeout=1.0)
        self.assertEqual(interface._webhook_url_from_payload(out), "https://example.com/hook")

    def test_webhook_present_without_autoclear_fails_closed(self):
        interface = TelegramCommandInterface(token="x", autoclear_webhook=False)
        webhook_payload = {
            "ok": True,
            "result": {
                "url": "https://example.com/hook",
                "pending_update_count": 3,
            },
        }
        with mock.patch.object(interface, "_api_get_json", return_value=webhook_payload):
            with self.assertRaises(TelegramWebhookConflictError):
                interface._ensure_webhook_ready()

    def test_webhook_present_with_autoclear_deletes_webhook(self):
        interface = TelegramCommandInterface(token="x", autoclear_webhook=True)
        webhook_payload = {
            "ok": True,
            "result": {
                "url": "https://example.com/hook",
                "pending_update_count": 5,
            },
        }
        with mock.patch.object(interface, "_api_get_json", return_value=webhook_payload), mock.patch.object(
            interface, "_api_post_json", return_value={"ok": True, "description": "Webhook was deleted"}
        ) as post_mock:
            interface._ensure_webhook_ready()
        post_mock.assert_called_once()
        _, kwargs = post_mock.call_args
        self.assertEqual(kwargs.get("drop_pending_updates"), "true")


if __name__ == "__main__":
    unittest.main()
