import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "workspace" / "scripts" / "render_trail_landscape.py"
    spec = importlib.util.spec_from_file_location("render_trail_landscape_module", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestRenderTrailLandscape(unittest.TestCase):
    def test_bucket_counts_with_fixture(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "trails.jsonl"
            rows = [
                {"trail_id": "a", "strength": 0.95, "source": "wander"},
                {"trail_id": "b", "strength": 0.50, "source": "task"},
                {"trail_id": "c", "strength": 0.10, "source": "response"},
                {"trail_id": "d", "strength": 0.81, "source": "wander"},
            ]
            path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            loaded = module.load_trails(path)
            counts = module.bucket_counts(loaded)
            self.assertEqual(counts, {"hot": 2, "fading": 1, "almost_gone": 1})


if __name__ == "__main__":
    unittest.main()

