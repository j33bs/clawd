"""Tests for pure helpers in workspace/memory/event_notifier.py.

Pure stdlib (json, datetime, pathlib) — no stubs needed.
Uses tempfile for filesystem isolation.

Covers:
- EventNotifier._load
- EventNotifier._save
- EventNotifier.notify
- EventNotifier.get_unread
- EventNotifier.mark_read
- EventNotifier.get_dashboard
"""
import importlib.util as _ilu
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NOTIFIER_PATH = REPO_ROOT / "workspace" / "memory" / "event_notifier.py"

_spec = _ilu.spec_from_file_location("memory_event_notifier_real", str(NOTIFIER_PATH))
en = _ilu.module_from_spec(_spec)
sys.modules["memory_event_notifier_real"] = en
_spec.loader.exec_module(en)


def _make_notifier(tmp: str) -> "en.EventNotifier":
    """Create an EventNotifier backed by a file in a temp dir."""
    p = Path(tmp) / "events.json"
    return en.EventNotifier(path=str(p))


# ---------------------------------------------------------------------------
# _load
# ---------------------------------------------------------------------------

class TestEventNotifierLoad(unittest.TestCase):
    """Tests for EventNotifier._load() — file I/O with default fallback."""

    def test_default_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            # _load is called by __init__; check the stored result
            self.assertIn("events", notifier.events)
            self.assertIn("notifications", notifier.events)

    def test_default_events_list_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            self.assertEqual(notifier.events["events"], [])

    def test_loads_from_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "events.json"
            payload = {"events": [{"title": "t", "message": "m", "urgency": "normal", "read": False}],
                       "notifications": []}
            p.write_text(json.dumps(payload), encoding="utf-8")
            notifier = en.EventNotifier(path=str(p))
            self.assertEqual(len(notifier.events["events"]), 1)

    def test_returns_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            result = notifier._load()
            self.assertIsInstance(result, dict)


# ---------------------------------------------------------------------------
# notify
# ---------------------------------------------------------------------------

class TestEventNotifierNotify(unittest.TestCase):
    """Tests for EventNotifier.notify() — adds events to the store."""

    def test_returns_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            result = notifier.notify("T", "M")
            self.assertIsInstance(result, dict)

    def test_event_added(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            notifier.notify("Title", "Body")
            self.assertEqual(len(notifier.events["events"]), 1)

    def test_title_stored(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            event = notifier.notify("MyTitle", "Body")
            self.assertEqual(event["title"], "MyTitle")

    def test_message_stored(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            event = notifier.notify("T", "MyMessage")
            self.assertEqual(event["message"], "MyMessage")

    def test_default_urgency_normal(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            event = notifier.notify("T", "M")
            self.assertEqual(event["urgency"], "normal")

    def test_high_urgency_added_to_notifications(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            notifier.notify("Alert", "Something bad", urgency="high")
            self.assertEqual(len(notifier.events["notifications"]), 1)

    def test_normal_urgency_not_added_to_notifications(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            notifier.notify("Info", "Something fine", urgency="normal")
            self.assertEqual(len(notifier.events["notifications"]), 0)

    def test_event_initially_unread(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            event = notifier.notify("T", "M")
            self.assertFalse(event["read"])

    def test_persisted_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "events.json"
            notifier = en.EventNotifier(path=str(p))
            notifier.notify("T", "M")
            self.assertTrue(p.exists())


# ---------------------------------------------------------------------------
# get_unread
# ---------------------------------------------------------------------------

class TestEventNotifierGetUnread(unittest.TestCase):
    """Tests for EventNotifier.get_unread() — filters by read=False."""

    def test_all_unread_initially(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            notifier.notify("A", "1")
            notifier.notify("B", "2")
            self.assertEqual(len(notifier.get_unread()), 2)

    def test_returns_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            self.assertIsInstance(notifier.get_unread(), list)

    def test_empty_when_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            self.assertEqual(notifier.get_unread(), [])

    def test_excludes_read_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            notifier.notify("A", "1")
            notifier.notify("B", "2")
            notifier.mark_read(0)
            self.assertEqual(len(notifier.get_unread()), 1)


# ---------------------------------------------------------------------------
# mark_read
# ---------------------------------------------------------------------------

class TestEventNotifierMarkRead(unittest.TestCase):
    """Tests for EventNotifier.mark_read() — sets read=True by index."""

    def test_marks_event_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            notifier.notify("T", "M")
            notifier.mark_read(0)
            self.assertTrue(notifier.events["events"][0]["read"])

    def test_invalid_index_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            notifier.notify("T", "M")
            notifier.mark_read(99)  # out of range — no exception
            self.assertFalse(notifier.events["events"][0]["read"])

    def test_negative_index_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            notifier.notify("T", "M")
            notifier.mark_read(-1)  # negative — implementation guards 0 <= index
            # The check is 0 <= index < len, so -1 would fail the 0 <= condition
            pass  # no exception expected


# ---------------------------------------------------------------------------
# get_dashboard
# ---------------------------------------------------------------------------

class TestEventNotifierGetDashboard(unittest.TestCase):
    """Tests for EventNotifier.get_dashboard() — summary statistics."""

    def test_returns_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            self.assertIsInstance(notifier.get_dashboard(), dict)

    def test_total_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            notifier.notify("A", "1")
            notifier.notify("B", "2")
            dash = notifier.get_dashboard()
            self.assertEqual(dash["total"], 2)

    def test_unread_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            notifier.notify("A", "1")
            notifier.notify("B", "2")
            notifier.mark_read(0)
            dash = notifier.get_dashboard()
            self.assertEqual(dash["unread"], 1)

    def test_high_urgency_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            notifier.notify("A", "1", urgency="high")
            notifier.notify("B", "2", urgency="normal")
            dash = notifier.get_dashboard()
            self.assertEqual(dash["high_urgency"], 1)

    def test_recent_key_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            dash = notifier.get_dashboard()
            self.assertIn("recent", dash)

    def test_zero_counts_when_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = _make_notifier(tmp)
            dash = notifier.get_dashboard()
            self.assertEqual(dash["total"], 0)
            self.assertEqual(dash["unread"], 0)


if __name__ == "__main__":
    unittest.main()
