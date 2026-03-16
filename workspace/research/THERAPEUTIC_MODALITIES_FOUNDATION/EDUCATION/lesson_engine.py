#!/usr/bin/env python3
"""Adaptive micro-lesson engine for Therapeutic Modalities Foundation.

Zone-of-proximal-development rules:
- one lesson at a time
- next lesson blocked until the prior one is answered
- difficulty rises when performance is solid/strong
- weak performance triggers scaffolded or same-skill follow-ups
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
LESSONS_PATH = ROOT / "micro_lessons.json"
STATE_PATH = ROOT / "lesson_state.json"

SCORE_MAP = {
    "incorrect": 0.0,
    "partial": 0.45,
    "solid": 0.75,
    "strong": 1.0,
}


@dataclass
class LessonEngine:
    lessons: list[dict[str, Any]]
    state: dict[str, Any]

    @classmethod
    def load(cls) -> "LessonEngine":
        lessons = json.loads(LESSONS_PATH.read_text())
        state = json.loads(STATE_PATH.read_text())
        return cls(lessons=lessons, state=state)

    @property
    def lesson_map(self) -> dict[str, dict[str, Any]]:
        return {lesson["id"]: lesson for lesson in self.lessons}

    def save(self) -> None:
        STATE_PATH.write_text(json.dumps(self.state, indent=2) + "\n")

    def _now(self) -> datetime:
        return datetime.now()

    def _reset_daily_counter_if_needed(self) -> None:
        today = self._now().date().isoformat()
        daily = self.state.setdefault("daily_delivery", {"date": None, "count": 0})
        if daily.get("date") != today:
            daily["date"] = today
            daily["count"] = 0

    def _within_window(self) -> bool:
        delivery = self.state.get("delivery", {})
        now = self._now()
        return int(delivery.get("earliest_hour", 9)) <= now.hour <= int(delivery.get("latest_hour", 19))

    def _min_gap_elapsed(self) -> bool:
        delivery = self.state.get("delivery", {})
        last = self.state.get("last_delivered_at")
        if not last:
            return True
        gap = int(delivery.get("min_gap_minutes", 90))
        return self._now() - datetime.fromisoformat(last) >= timedelta(minutes=gap)

    def _daily_capacity_available(self) -> bool:
        self._reset_daily_counter_if_needed()
        daily = self.state.get("daily_delivery", {})
        limit = int(self.state.get("delivery", {}).get("max_lessons_per_day", 6))
        return int(daily.get("count", 0)) < limit

    def _lesson_seen(self, lesson_id: str) -> bool:
        return any(str(item.get("lesson_id")) == lesson_id for item in self.state.get("lesson_history", []))

    def _skill_score(self, skill: str) -> float:
        proficiency = self.state.setdefault("proficiency", {})
        return float(proficiency.get(skill, 0.0))

    def _update_skill_score(self, skill: str, outcome: str) -> None:
        current = self._skill_score(skill)
        observed = SCORE_MAP[outcome]
        updated = (current * 0.7) + (observed * 0.3)
        self.state.setdefault("proficiency", {})[skill] = round(updated, 3)

    def _eligible_lessons(self) -> list[dict[str, Any]]:
        active = self.state.get("active_lesson_id")
        if active:
            return []
        return [lesson for lesson in self.lessons if not self._lesson_seen(lesson["id"])]

    def _choose_seed(self) -> dict[str, Any] | None:
        for lesson in self.lessons:
            if lesson["difficulty"] == 1 and not self._lesson_seen(lesson["id"]):
                return lesson
        return None

    def _choose_from_followups(self, prior: dict[str, Any], outcome: str) -> dict[str, Any] | None:
        key = f"follow_if_{outcome}"
        for lesson_id in prior.get(key, []):
            lesson = self.lesson_map.get(lesson_id)
            if lesson and not self._lesson_seen(lesson_id):
                return lesson
        return None

    def _choose_adaptive(self) -> dict[str, Any] | None:
        candidates = self._eligible_lessons()
        if not candidates:
            return None

        def candidate_rank(lesson: dict[str, Any]) -> tuple[float, int, str]:
            skill_score = self._skill_score(lesson["skill"])
            difficulty = int(lesson.get("difficulty", 1))
            target = 1.0 + round(skill_score * 4)
            distance = abs(difficulty - target)
            return (distance, difficulty, lesson["id"])

        return sorted(candidates, key=candidate_rank)[0]

    def next_lesson(self) -> dict[str, Any] | None:
        if self.state.get("awaiting_answer"):
            active = self.lesson_map.get(self.state.get("active_lesson_id"))
            return {"status": "awaiting_answer", "lesson": active}
        if not self._within_window() or not self._min_gap_elapsed() or not self._daily_capacity_available():
            return None

        history = self.state.get("lesson_history", [])
        prior = self.lesson_map.get(history[-1]["lesson_id"]) if history else None
        outcome = history[-1].get("outcome") if history else None

        lesson = None
        if prior and outcome:
            lesson = self._choose_from_followups(prior, outcome)
        if lesson is None and not history:
            lesson = self._choose_seed()
        if lesson is None:
            lesson = self._choose_adaptive()
        if lesson is None:
            return None

        now = self._now().isoformat(timespec="seconds")
        self.state["awaiting_answer"] = True
        self.state["active_lesson_id"] = lesson["id"]
        self.state["last_delivered_at"] = now
        self._reset_daily_counter_if_needed()
        self.state["daily_delivery"]["count"] += 1
        self.save()
        return {"status": "deliver", "lesson": lesson}

    def record_answer(self, outcome: str, answer: str) -> dict[str, Any]:
        if outcome not in SCORE_MAP:
            raise ValueError("outcome must be one of incorrect|partial|solid|strong")
        lesson_id = self.state.get("active_lesson_id")
        if not lesson_id:
            raise ValueError("no active lesson")
        lesson = self.lesson_map[lesson_id]
        self._update_skill_score(lesson["skill"], outcome)
        event = {
            "lesson_id": lesson_id,
            "skill": lesson["skill"],
            "difficulty": lesson.get("difficulty", 1),
            "answered_at": self._now().isoformat(timespec="seconds"),
            "outcome": outcome,
            "answer": answer,
        }
        self.state.setdefault("lesson_history", []).append(event)
        self.state["awaiting_answer"] = False
        self.state["active_lesson_id"] = None
        self.state["last_answered_at"] = event["answered_at"]
        self.save()
        return event


def print_lesson(lesson: dict[str, Any]) -> None:
    print(f"[{lesson['id']}] difficulty={lesson['difficulty']} kind={lesson['kind']}")
    print(lesson["prompt"])
    hints = lesson.get("hints") or []
    if hints:
        print(f"Hint: {hints[0]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("next")
    ans = sub.add_parser("answer")
    ans.add_argument("outcome", choices=list(SCORE_MAP))
    ans.add_argument("answer")
    sub.add_parser("state")
    args = parser.parse_args()

    engine = LessonEngine.load()

    if args.cmd == "next":
        result = engine.next_lesson()
        if result is None:
            print("NO_LESSON_READY")
            return
        if result["status"] == "awaiting_answer":
            print("AWAITING_ANSWER")
            print_lesson(result["lesson"])
            return
        print_lesson(result["lesson"])
        return

    if args.cmd == "answer":
        event = engine.record_answer(args.outcome, args.answer)
        print(json.dumps(event, indent=2))
        return

    if args.cmd == "state":
        print(json.dumps(engine.state, indent=2))


if __name__ == "__main__":
    main()
