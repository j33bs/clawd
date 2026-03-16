import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    path = REPO_ROOT / "workspace" / "scripts" / "grok_evolver.py"
    spec = importlib.util.spec_from_file_location("grok_evolver", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class GrokEvolverTests(unittest.TestCase):
    def _build_repo(self, root: Path) -> None:
        (root / "workspace" / "policy").mkdir(parents=True, exist_ok=True)
        (root / "workspace" / "scripts").mkdir(parents=True, exist_ok=True)
        (root / "itc").mkdir(parents=True, exist_ok=True)

        policy = {
            "routing": {
                "capability_router": {
                    "chatProvider": "grok_api",
                    "planningProvider": "grok_api",
                    "reasoningProvider": "grok_api",
                    "codeProvider": "grok_api",
                    "smallCodeProvider": "local_vllm_assistant",
                    "localChatMaxChars": 320,
                    "reasoningEscalationTokens": 1400,
                }
            }
        }
        (root / "workspace" / "policy" / "llm_policy.json").write_text(
            json.dumps(policy, indent=2) + "\n", encoding="utf-8"
        )
        rows = [
            {"event": "router_success", "detail": {"provider": "grok_api"}},
            {"event": "router_success", "detail": {"provider": "grok_api"}},
            {"event": "router_success", "detail": {"provider": "local_vllm_assistant"}},
        ]
        (root / "itc" / "llm_router_events.jsonl").write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
        )
        stub = """#!/usr/bin/env python3
import argparse
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--max-files')
parser.add_argument('--out')
args = parser.parse_args()
Path(args.out).write_text('# snapshot\\n', encoding='utf-8')
"""
        (root / "workspace" / "scripts" / "report_token_burn.py").write_text(stub, encoding="utf-8")

    def test_generates_report_and_json(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._build_repo(root)
            result = module.run(root, apply_safe=False)
            self.assertTrue(result.report_path.exists())
            self.assertTrue(result.json_path.exists())
            text = result.report_path.read_text(encoding="utf-8")
            self.assertIn("Grok Evolver Report", text)
            self.assertIn("localChatMaxChars", text)

    def test_apply_safe_adjusts_local_chat_threshold(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._build_repo(root)
            extra = [
                {"event": "router_escalate", "detail": {"reason_code": "context_too_large_for_local"}},
                {"event": "router_escalate", "detail": {"reason_code": "context_too_large_for_local"}},
                {"event": "router_escalate", "detail": {"reason_code": "context_too_large_for_local"}},
                {"event": "router_escalate", "detail": {"reason_code": "context_too_large_for_local"}},
                {"event": "router_escalate", "detail": {"reason_code": "context_too_large_for_local"}},
            ]
            path = root / "itc" / "llm_router_events.jsonl"
            with path.open("a", encoding="utf-8") as handle:
                for row in extra:
                    handle.write(json.dumps(row) + "\n")
            result = module.run(root, apply_safe=True)
            self.assertIn("localChatMaxChars", result.applied)
            updated = json.loads((root / "workspace" / "policy" / "llm_policy.json").read_text(encoding="utf-8"))
            self.assertEqual(updated["routing"]["capability_router"]["localChatMaxChars"], 280)


if __name__ == "__main__":
    unittest.main()
