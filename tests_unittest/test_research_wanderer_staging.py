import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "workspace" / "scripts" / "research_wanderer.py"
    spec = importlib.util.spec_from_file_location("research_wanderer_module_staging", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestResearchWandererStaging(unittest.TestCase):
    def test_threshold_and_philosophy_tags_stage_draft(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            selected = [
                module.QuestionCandidate(text="What ontology constraints should guide routing?", significance=0.91),
            ]
            result = module.stage_open_questions_draft(
                session_id="sess-stage",
                run_id="run-stage",
                trigger="cron",
                score=0.9,
                threshold=0.65,
                selected=selected,
                trail_ids=["trail-1"],
                drafts_dir=base / "drafts",
                index_path=base / "drafts" / "index.jsonl",
                dry_run=False,
            )
            self.assertTrue(result["staged"])
            self.assertTrue((base / "drafts" / "sess-stage.md").exists())
            self.assertTrue((base / "drafts" / "index.jsonl").exists())

    def test_non_threshold_or_non_tagged_does_not_stage(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            selected = [module.QuestionCandidate(text="How should we improve routing confidence?", significance=0.9)]
            result = module.stage_open_questions_draft(
                session_id="sess-no-stage",
                run_id="run-no-stage",
                trigger="task",
                score=0.5,
                threshold=0.65,
                selected=selected,
                trail_ids=["trail-2"],
                drafts_dir=base / "drafts",
                index_path=base / "drafts" / "index.jsonl",
                dry_run=False,
            )
            self.assertFalse(result["staged"])
            self.assertFalse((base / "drafts" / "sess-no-stage.md").exists())


if __name__ == "__main__":
    unittest.main()

