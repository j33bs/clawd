import ast
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestPython39CompatPolicyRouterImport(unittest.TestCase):
    def test_policy_router_parses_with_python39_grammar(self):
        src = (REPO_ROOT / "workspace" / "scripts" / "policy_router.py").read_text(encoding="utf-8")
        ast.parse(src, filename="policy_router.py", feature_version=(3, 9))


if __name__ == "__main__":
    unittest.main()
