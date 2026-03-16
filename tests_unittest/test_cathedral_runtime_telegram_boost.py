import unittest
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.runtime import DaliCathedralRuntime


class TestTelegramBoostParsing(unittest.TestCase):
    def test_parse_value_ttl_defaults_and_clamps(self):
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        value, ttl = runtime._parse_value_ttl("", default_value=1.8, default_seconds=30.0)
        self.assertAlmostEqual(value, 1.8)
        self.assertAlmostEqual(ttl, 30.0)

        value, ttl = runtime._parse_value_ttl("2.5 999", default_value=1.8, default_seconds=30.0)
        self.assertAlmostEqual(value, 2.5)
        self.assertAlmostEqual(ttl, 300.0)

        value, ttl = runtime._parse_value_ttl("bad 1", default_value=1.8, default_seconds=30.0)
        self.assertAlmostEqual(value, 1.8)
        self.assertAlmostEqual(ttl, 2.0)


if __name__ == "__main__":
    unittest.main()
