import tempfile
import unittest
from pathlib import Path

from workspace.discord_surface.bridge import load_delivery_state, payload_hash, record_delivery, should_skip_delivery


class TestDiscordBridge(unittest.TestCase):
    def test_payload_hash_changes_with_content(self):
        self.assertNotEqual(payload_hash("one"), payload_hash("two"))

    def test_dedup_skips_unchanged_payload(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "bridge_state.json"
            state = load_delivery_state(state_path)
            self.assertFalse(should_skip_delivery(state, "ops_status", "hello"))
            record_delivery(state_path, state, "ops_status", "hello", status="ok")
            reloaded = load_delivery_state(state_path)
            self.assertTrue(should_skip_delivery(reloaded, "ops_status", "hello"))
            self.assertFalse(should_skip_delivery(reloaded, "ops_status", "goodbye"))


if __name__ == "__main__":
    unittest.main()

