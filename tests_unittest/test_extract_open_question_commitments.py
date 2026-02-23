import importlib.util
import sys
import unittest
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "workspace" / "scripts" / "extract_open_question_commitments.py"
    spec = importlib.util.spec_from_file_location("extract_commitments_module", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestExtractOpenQuestionCommitments(unittest.TestCase):
    def test_extracts_expected_commitment_lines(self):
        module = _load_module()
        text = """# Open Questions

## Session A
1. I will test this before next audit.
2. speculative question

### Follow-up
- We are committed to closing the loop.
"""
        items = module.extract_commitments(text)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["line"], 4)
        self.assertIn("Session A", items[0]["section_path"])
        self.assertIn("Follow-up", items[1]["section_path"])


if __name__ == "__main__":
    unittest.main()

