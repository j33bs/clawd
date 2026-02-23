import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

import message_handler  # noqa: E402


class MessageHandlerPairingPreflightTests(unittest.IsolatedAsyncioTestCase):
    async def test_spawn_blocked_returns_structured_pairing_error(self):
        blocked = {
            "ok": False,
            "reason": "PAIRING_REMOTE_REQUIRED",
            "remedy": "run pairing check",
            "observations": {"guard_rc": 3},
        }
        with patch.object(message_handler, "ensure_pairing_healthy", return_value=blocked), patch.object(
            message_handler, "_append_gate_event", return_value={"ok": True}
        ) as gate_event, patch.object(message_handler, "_spawn_once", new=AsyncMock()) as spawn_once:
            result = await message_handler.spawn_chatgpt_subagent(
                task="sensitive prompt should not leak",
                context={},
                gateway_url="http://127.0.0.1:18789",
                token="",
            )
        self.assertFalse(result.get("ok"))
        err = result.get("error", {})
        self.assertEqual(err.get("type"), "PAIRING_UNHEALTHY")
        self.assertEqual(err.get("tier"), "LOCAL")
        self.assertIn("confidence", err)
        self.assertIn("remediation", err)
        self.assertIn("observations", err)
        self.assertIn("corr_id", err)
        self.assertNotIn("sensitive prompt should not leak", json.dumps(result))
        gate_event.assert_called_once()
        spawn_once.assert_not_called()

    async def test_spawn_retries_once_after_stale_refresh(self):
        ensure_seq = [
            {"ok": True, "reason": "PAIRING_STALE", "safe_to_retry_now": True},
            {"ok": True, "reason": "OK"},
        ]
        spawn_once = AsyncMock(side_effect=[{"error": "pairing required"}, {"response": "done"}])
        with patch.object(message_handler, "ensure_pairing_healthy", side_effect=ensure_seq), patch.object(
            message_handler, "_spawn_once", new=spawn_once
        ):
            result = await message_handler.spawn_chatgpt_subagent(
                task="hello",
                context={},
                gateway_url="http://127.0.0.1:18789",
                token="",
            )
        self.assertEqual(result.get("response"), "done")
        self.assertEqual(spawn_once.await_count, 2)


if __name__ == "__main__":
    unittest.main()
