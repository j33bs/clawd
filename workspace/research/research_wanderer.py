#!/usr/bin/env python3
"""Compatibility wrapper for workspace/scripts/research_wanderer.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "research_wanderer.py"
SPEC = importlib.util.spec_from_file_location("_workspace_scripts_research_wanderer", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError(f"unable to load research wanderer script from {SCRIPT_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

NoveltyDecision = MODULE.NoveltyDecision
append_open_questions = MODULE.append_open_questions
do_wander = MODULE.do_wander
evaluate_novelty = MODULE.evaluate_novelty
generate_candidate_question = MODULE.generate_candidate_question
load_recent_questions = MODULE.load_recent_questions
main = MODULE.main
parse_open_questions = MODULE.parse_open_questions
parse_wander_log_questions = MODULE.parse_wander_log_questions
pick_open_loop = MODULE.pick_open_loop
select_question = MODULE.select_question


if __name__ == "__main__":
    raise SystemExit(main())
