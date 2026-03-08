"""Tests for workspace/memory_ext/tailscale_agent.py pure helpers.

Covers (no actual tailscale/network, env-guarded):
- _tailscale_enabled
- MeshNode.ping / send_message / relay_via (disabled path)
- mesh_broadcast (disabled path)
- relay_to_agent (disabled path)
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = REPO_ROOT / "workspace"
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from memory_ext.tailscale_agent import (  # noqa: E402
    MeshNode,
    _tailscale_enabled,
    mesh_broadcast,
    relay_to_agent,
)


# ---------------------------------------------------------------------------
# _tailscale_enabled
# ---------------------------------------------------------------------------

class TestTailscaleEnabled(unittest.TestCase):
    """Tests for _tailscale_enabled() — env var flag."""

    def test_disabled_by_default_zero(self):
        with patch.dict(os.environ, {"OPENCLAW_TAILSCALE": "0"}, clear=False):
            self.assertFalse(_tailscale_enabled())

    def test_enabled_by_one(self):
        with patch.dict(os.environ, {"OPENCLAW_TAILSCALE": "1"}, clear=False):
            self.assertTrue(_tailscale_enabled())

    def test_returns_bool(self):
        self.assertIsInstance(_tailscale_enabled(), bool)

    def test_non_one_disabled(self):
        with patch.dict(os.environ, {"OPENCLAW_TAILSCALE": "true"}, clear=False):
            # Only "1" is enabled; "true" is not
            self.assertFalse(_tailscale_enabled())


# ---------------------------------------------------------------------------
# MeshNode (disabled path)
# ---------------------------------------------------------------------------

class TestMeshNodeDisabled(unittest.TestCase):
    """Tests for MeshNode methods when tailscale is disabled."""

    def setUp(self):
        self._node = MeshNode(node_id="test-node")

    def test_ping_disabled_returns_ok_false(self):
        with patch.dict(os.environ, {"OPENCLAW_TAILSCALE": "0"}, clear=False):
            result = self._node.ping("peer1")
            self.assertFalse(result["ok"])

    def test_ping_disabled_reason(self):
        with patch.dict(os.environ, {"OPENCLAW_TAILSCALE": "0"}, clear=False):
            result = self._node.ping("peer1")
            self.assertEqual(result["reason"], "tailscale_disabled")

    def test_ping_node_field_returned(self):
        with patch.dict(os.environ, {"OPENCLAW_TAILSCALE": "0"}, clear=False):
            result = self._node.ping("peer1")
            self.assertEqual(result["node"], "peer1")

    def test_send_message_disabled_ok_false(self):
        with patch.dict(os.environ, {"OPENCLAW_TAILSCALE": "0"}, clear=False):
            result = self._node.send_message("peer1", "hello")
            self.assertFalse(result["ok"])

    def test_send_message_preserves_message(self):
        with patch.dict(os.environ, {"OPENCLAW_TAILSCALE": "0"}, clear=False):
            result = self._node.send_message("peer1", "my_message")
            self.assertEqual(result["message"], "my_message")

    def test_relay_via_disabled_ok_false(self):
        with patch.dict(os.environ, {"OPENCLAW_TAILSCALE": "0"}, clear=False):
            result = self._node.relay_via("relay_node", "msg")
            self.assertFalse(result["ok"])

    def test_relay_via_preserves_via(self):
        with patch.dict(os.environ, {"OPENCLAW_TAILSCALE": "0"}, clear=False):
            result = self._node.relay_via("relay_node", "msg")
            self.assertEqual(result["via"], "relay_node")


# ---------------------------------------------------------------------------
# mesh_broadcast (disabled path)
# ---------------------------------------------------------------------------

class TestMeshBroadcastDisabled(unittest.TestCase):
    """Tests for mesh_broadcast() when tailscale is disabled."""

    def test_returns_disabled_status(self):
        with patch.dict(os.environ, {"OPENCLAW_TAILSCALE": "0"}, clear=False):
            result = mesh_broadcast("hello")
            self.assertEqual(result["status"], "disabled")

    def test_delivered_to_empty(self):
        with patch.dict(os.environ, {"OPENCLAW_TAILSCALE": "0"}, clear=False):
            result = mesh_broadcast("hello")
            self.assertEqual(result["delivered_to"], [])

    def test_ttl_preserved(self):
        with patch.dict(os.environ, {"OPENCLAW_TAILSCALE": "0"}, clear=False):
            result = mesh_broadcast("msg", ttl=5)
            self.assertEqual(result["ttl"], 5)

    def test_returns_dict(self):
        with patch.dict(os.environ, {"OPENCLAW_TAILSCALE": "0"}, clear=False):
            self.assertIsInstance(mesh_broadcast("msg"), dict)


# ---------------------------------------------------------------------------
# relay_to_agent (disabled path)
# ---------------------------------------------------------------------------

class TestRelayToAgentDisabled(unittest.TestCase):
    """Tests for relay_to_agent() when tailscale is disabled."""

    def test_ok_false_when_disabled(self):
        with patch.dict(os.environ, {"OPENCLAW_TAILSCALE": "0"}, clear=False):
            result = relay_to_agent("10.0.0.1", "msg")
            self.assertFalse(result["ok"])

    def test_target_ip_preserved(self):
        with patch.dict(os.environ, {"OPENCLAW_TAILSCALE": "0"}, clear=False):
            result = relay_to_agent("10.0.0.1", "msg")
            self.assertEqual(result["target_ip"], "10.0.0.1")

    def test_reason_present(self):
        with patch.dict(os.environ, {"OPENCLAW_TAILSCALE": "0"}, clear=False):
            result = relay_to_agent("10.0.0.1", "msg")
            self.assertIn("reason", result)

    def test_returns_dict(self):
        with patch.dict(os.environ, {"OPENCLAW_TAILSCALE": "0"}, clear=False):
            self.assertIsInstance(relay_to_agent("ip", "msg"), dict)


if __name__ == "__main__":
    unittest.main()
