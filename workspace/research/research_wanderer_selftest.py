#!/usr/bin/env python3
import importlib.util
import tempfile
from datetime import timezone
from pathlib import Path


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("research_wanderer", str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def configure_tmp(module, tmp_dir: Path):
    module.OPEN_QUESTIONS_FILE = tmp_dir / "OPEN_QUESTIONS.md"
    module.OPEN_QUESTIONS_INDEX_FILE = tmp_dir / "OPEN_QUESTIONS_INDEX.md"
    module.OPEN_QUESTIONS_SHARDS_DIR = tmp_dir / "open_questions_shards"
    module.OPEN_QUESTIONS_LOCK_FILE = tmp_dir / ".open_questions.lock"
    module.QUESTION_COOLDOWN_HOURS = 0
    module.QUESTION_DEDUPE_DAYS = 14
    module.QUESTION_STATE_TTL_DAYS = 90
    module.OPEN_QUESTIONS_LOCK_TIMEOUT_SEC = 2


def main():
    module_path = Path(__file__).with_name("research_wanderer.py")
    mod = load_module(module_path)

    with tempfile.TemporaryDirectory(prefix="rw-selftest-") as tmp:
        tmp_dir = Path(tmp)
        configure_tmp(mod, tmp_dir)

        findings = {"open_questions_state": {}}
        now_utc = mod._utc_now().astimezone(timezone.utc)

        ok1, reason1 = mod.maybe_append_open_question(
            findings,
            "What would temporal routing mean for TACTI(C)-R?",
            "temporality",
            now_utc,
        )
        assert ok1 and reason1 == "appended", (ok1, reason1)

        ok2, reason2 = mod.maybe_append_open_question(
            findings,
            "  What would temporal routing mean for TACTI(C)-R?  ",
            "temporality",
            now_utc,
        )
        assert (not ok2) and reason2 == "duplicate_recent", (ok2, reason2)

        ok3, reason3 = mod.maybe_append_open_question(
            findings,
            "What would temporal routing mean for TACTI(C)-R?",
            "cross_timescale",
            now_utc,
        )
        assert ok3 and reason3 == "appended", (ok3, reason3)

        ok4, reason4 = mod.maybe_append_open_question(
            findings,
            "What would collapse detection mean for TACTI(C)-R?",
            "collapse",
            now_utc,
        )
        assert ok4 and reason4 == "appended", (ok4, reason4)

        assert mod.OPEN_QUESTIONS_LOCK_FILE.exists(), "lock file missing"

        lines = mod.OPEN_QUESTIONS_FILE.read_text(encoding="utf-8")
        assert lines.count("Question:") == 3, lines

    print("PASS research_wanderer self-test")


if __name__ == "__main__":
    main()
