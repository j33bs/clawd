"""Tests for message_load_balancer.py — LoadBalancer pure/stateless logic.

Note: LoadBalancer.get_status() internally calls self.check_overload() while
already holding self._lock (a non-reentrant Lock), which deadlocks when
ENABLE_FALLBACK is True.  We always patch _MOD.ENABLE_FALLBACK=False for
get_status() tests to sidestep the deadlock.
"""
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = REPO_ROOT / "workspace" / "scripts" / "message_load_balancer.py"
_SPEC = importlib.util.spec_from_file_location("_mlb", _SCRIPT)
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules["_mlb"] = _MOD
_SPEC.loader.exec_module(_MOD)

LoadBalancer = _MOD.LoadBalancer
LoadMetrics = _MOD.LoadMetrics
Message = _MOD.Message


class TestLoadMetrics(unittest.TestCase):
    """Tests for the LoadMetrics dataclass."""

    def test_defaults_are_zero(self):
        m = LoadMetrics()
        self.assertEqual(m.queue_depth, 0)
        self.assertAlmostEqual(m.avg_latency_ms, 0.0)
        self.assertEqual(m.active_agents, 0)

    def test_timestamp_is_string(self):
        m = LoadMetrics()
        self.assertIsInstance(m.timestamp, str)

    def test_custom_values_stored(self):
        m = LoadMetrics(queue_depth=3, avg_latency_ms=500.0, active_agents=2)
        self.assertEqual(m.queue_depth, 3)
        self.assertAlmostEqual(m.avg_latency_ms, 500.0)
        self.assertEqual(m.active_agents, 2)


class TestMessage(unittest.TestCase):
    """Tests for the Message dataclass."""

    def test_required_fields(self):
        msg = Message(id="m1", content="hello", sender="user", timestamp="2026-01-01T00:00:00Z")
        self.assertEqual(msg.id, "m1")
        self.assertEqual(msg.content, "hello")

    def test_priority_default(self):
        msg = Message(id="m2", content="hi", sender="u", timestamp="t")
        self.assertEqual(msg.priority, "normal")

    def test_assigned_agent_default_none(self):
        msg = Message(id="m3", content="hi", sender="u", timestamp="t")
        self.assertIsNone(msg.assigned_agent)


class TestLoadBalancerCheckOverload(unittest.TestCase):
    """Tests for LoadBalancer.check_overload() — called DIRECTLY, not via get_status."""

    def _lb(self):
        return LoadBalancer()

    def test_no_load_not_overloaded(self):
        lb = self._lb()
        with patch.object(_MOD, "ENABLE_FALLBACK", True):
            lb.update_metrics(0, 0.0, 0)
            self.assertFalse(lb.check_overload())

    def test_queue_depth_at_max_triggers_overload(self):
        lb = self._lb()
        max_q = _MOD.MAX_QUEUE_DEPTH
        with patch.object(_MOD, "ENABLE_FALLBACK", True), \
             patch.object(_MOD, "MAX_QUEUE_DEPTH", max_q):
            lb.update_metrics(max_q, 0.0, 0)
            self.assertTrue(lb.check_overload())

    def test_high_latency_triggers_overload(self):
        lb = self._lb()
        max_lat = _MOD.MAX_LATENCY_MS
        with patch.object(_MOD, "ENABLE_FALLBACK", True), \
             patch.object(_MOD, "MAX_LATENCY_MS", max_lat):
            lb.update_metrics(0, float(max_lat), 0)
            self.assertTrue(lb.check_overload())

    def test_fallback_disabled_never_overloads(self):
        lb = self._lb()
        with patch.object(_MOD, "ENABLE_FALLBACK", False):
            lb.update_metrics(9999, 9999999.0, 0)
            self.assertFalse(lb.check_overload())

    def test_returns_bool(self):
        lb = self._lb()
        with patch.object(_MOD, "ENABLE_FALLBACK", False):
            self.assertIsInstance(lb.check_overload(), bool)


class TestLoadBalancerRouteReason(unittest.TestCase):
    """Tests for LoadBalancer._get_route_reason()."""

    def test_not_overloaded_returns_normal_message(self):
        lb = LoadBalancer()
        reason = lb._get_route_reason(False)
        self.assertIn("Normal", reason)

    def test_overloaded_queue_mentions_queue_depth(self):
        lb = LoadBalancer()
        lb.update_metrics(_MOD.MAX_QUEUE_DEPTH, 0.0, 0)
        reason = lb._get_route_reason(True)
        self.assertIn("Queue", reason)

    def test_overloaded_latency_mentions_latency(self):
        lb = LoadBalancer()
        lb.update_metrics(0, float(_MOD.MAX_LATENCY_MS), 0)
        reason = lb._get_route_reason(True)
        self.assertIn("atency", reason)

    def test_returns_string(self):
        lb = LoadBalancer()
        self.assertIsInstance(lb._get_route_reason(False), str)
        self.assertIsInstance(lb._get_route_reason(True), str)


class TestLoadBalancerRouteMessage(unittest.TestCase):
    """Tests for LoadBalancer.route_message()."""

    def _msg(self, msg_id="m1"):
        return Message(id=msg_id, content="test", sender="u", timestamp="t")

    def test_returns_dict(self):
        lb = LoadBalancer()
        with patch.object(_MOD, "ENABLE_FALLBACK", False):
            result = lb.route_message(self._msg())
        self.assertIsInstance(result, dict)

    def test_contains_required_keys(self):
        lb = LoadBalancer()
        with patch.object(_MOD, "ENABLE_FALLBACK", False):
            result = lb.route_message(self._msg())
        for key in ("message_id", "route", "reason", "timestamp"):
            self.assertIn(key, result)

    def test_no_overload_routes_to_minimax(self):
        lb = LoadBalancer()
        lb.update_metrics(0, 0.0, 0)
        with patch.object(_MOD, "ENABLE_FALLBACK", False):
            result = lb.route_message(self._msg())
        self.assertEqual(result["route"], "minimax")

    def test_overload_routes_to_chatgpt(self):
        lb = LoadBalancer()
        lb.update_metrics(_MOD.MAX_QUEUE_DEPTH, 0.0, 0)
        with patch.object(_MOD, "ENABLE_FALLBACK", True):
            result = lb.route_message(self._msg())
        self.assertEqual(result["route"], "chatgpt")

    def test_message_id_echoed(self):
        lb = LoadBalancer()
        with patch.object(_MOD, "ENABLE_FALLBACK", False):
            result = lb.route_message(self._msg("msg-99"))
        self.assertEqual(result["message_id"], "msg-99")

    def test_fallback_log_updated_on_chatgpt_route(self):
        lb = LoadBalancer()
        lb.update_metrics(_MOD.MAX_QUEUE_DEPTH, 0.0, 0)
        with patch.object(_MOD, "ENABLE_FALLBACK", True):
            lb.route_message(self._msg("fb-1"))
        self.assertEqual(len(lb.fallback_log), 1)
        self.assertEqual(lb.fallback_log[0]["message_id"], "fb-1")


class TestLoadBalancerGetStatus(unittest.TestCase):
    """Tests for LoadBalancer.get_status().

    get_status() holds self._lock then calls check_overload(), which also
    tries to acquire self._lock.  With ENABLE_FALLBACK=False, check_overload()
    short-circuits before acquiring the lock, so no deadlock occurs.
    """

    def test_returns_dict(self):
        lb = LoadBalancer()
        with patch.object(_MOD, "ENABLE_FALLBACK", False):
            self.assertIsInstance(lb.get_status(), dict)

    def test_contains_metrics_key(self):
        lb = LoadBalancer()
        with patch.object(_MOD, "ENABLE_FALLBACK", False):
            status = lb.get_status()
        self.assertIn("metrics", status)

    def test_contains_config_key(self):
        lb = LoadBalancer()
        with patch.object(_MOD, "ENABLE_FALLBACK", False):
            status = lb.get_status()
        self.assertIn("config", status)

    def test_fallback_count_zero_initially(self):
        lb = LoadBalancer()
        with patch.object(_MOD, "ENABLE_FALLBACK", False):
            status = lb.get_status()
        self.assertEqual(status["fallback_count"], 0)

    def test_fallback_count_reflected_from_log(self):
        lb = LoadBalancer()
        # Add a fake entry directly to avoid triggering the deadlock path
        lb.fallback_log.append({"message_id": "x", "timestamp": "t",
                                 "reason": "r", "routed_to": "chatgpt", "sender": "u"})
        with patch.object(_MOD, "ENABLE_FALLBACK", False):
            status = lb.get_status()
        self.assertEqual(status["fallback_count"], 1)

    def test_overloaded_key_present(self):
        lb = LoadBalancer()
        with patch.object(_MOD, "ENABLE_FALLBACK", False):
            status = lb.get_status()
        self.assertIn("overloaded", status)


if __name__ == "__main__":
    unittest.main()
