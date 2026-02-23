import json
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "workspace" / "scripts" / "build_session_context.py"
    spec = importlib.util.spec_from_file_location("build_session_context_module", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestSessionContextAssembler(unittest.TestCase):
    def test_extract_markdown_headings(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "SOUL.md"
            path.write_text("# Root\n\n## Values\nText\n### Constraints\n", encoding="utf-8")
            headings = module.extract_markdown_headings(path, max_headings=3)
            self.assertEqual(headings, ["Root", "Values", "Constraints"])

    def test_top_k_trails_sorted_by_strength(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as td:
            trail_path = Path(td) / "trails.jsonl"
            rows = [
                {"trail_id": "t-low", "strength": 0.2, "source": "task", "updated_at": "2026-02-23T00:00:00Z"},
                {"trail_id": "t-high", "strength": 0.9, "source": "wander", "updated_at": "2026-02-23T00:00:00Z"},
                {"trail_id": "t-mid", "strength": 0.5, "source": "response", "updated_at": "2026-02-23T00:00:00Z"},
            ]
            trail_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            top = module.select_top_trails_by_strength(trail_path, k=2)
            self.assertEqual([x["trail_id"] for x in top], ["t-high", "t-mid"])


if __name__ == "__main__":
    unittest.main()
