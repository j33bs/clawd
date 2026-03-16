import unittest
from datetime import datetime

from workspace.common.stochastic import bounded_randint, next_time_in_window, pick_with_cooldown


class TestStochastic(unittest.TestCase):
    def test_bounded_randint_respects_range(self):
        value = bounded_randint(45, 180, seed=7)
        self.assertGreaterEqual(value, 45)
        self.assertLessEqual(value, 180)

    def test_next_time_in_window_returns_bounded_future(self):
        now = datetime(2026, 3, 16, 10, 0, 0)
        choice = next_time_in_window(now=now, min_gap_minutes=45, max_gap_minutes=180, seed=11)
        delta = choice.value - now
        mins = int(delta.total_seconds() // 60)
        self.assertGreaterEqual(mins, 45)
        self.assertLessEqual(mins, 180)
        self.assertEqual(choice.rationale["kind"], "next_time_in_window")

    def test_pick_with_cooldown_prefers_non_cooled_items_when_available(self):
        items = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        choice = pick_with_cooldown(items, cooldown_ids={"a", "b"}, seed=3)
        self.assertEqual(choice.value["id"], "c")
        self.assertEqual(choice.rationale["kind"], "pick_with_cooldown")


if __name__ == "__main__":
    unittest.main()
