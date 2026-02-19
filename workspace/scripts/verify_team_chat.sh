#!/bin/bash
set -e

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT_DIR="/tmp/teamchat_verify"
SESSION_ID="verify_teamchat_offline"

rm -rf "$OUT_DIR"

python3 "$REPO_ROOT/workspace/scripts/team_chat.py" \
  --task "Verify offline planner+coder handoff" \
  --session-id "$SESSION_ID" \
  --output-root "$OUT_DIR" \
  --max-cycles 2 \
  --max-commands-per-cycle 3

python3 - <<'PY'
import json
from pathlib import Path

out = Path('/tmp/teamchat_verify')
session = out / 'sessions' / 'verify_teamchat_offline.jsonl'
summary = out / 'summaries' / 'verify_teamchat_offline.md'
state = out / 'state' / 'verify_teamchat_offline.json'

assert session.exists(), session
assert summary.exists(), summary
assert state.exists(), state

rows = [json.loads(line) for line in session.read_text(encoding='utf-8').splitlines() if line.strip()]
assert any(r.get('event') == 'planner_plan' for r in rows), 'missing planner_plan'
assert any(r.get('event') == 'patch_report' for r in rows), 'missing patch_report'
assert any(r.get('event') == 'tool_call' for r in rows), 'missing tool_call'
assert any(r.get('event') == 'planner_review' for r in rows), 'missing planner_review'

for row in rows:
    assert 'meta' in row and 'route' in row['meta'], row

state_obj = json.loads(state.read_text(encoding='utf-8'))
assert state_obj.get('status') in {'accepted', 'request_input', 'stopped:max_cycles', 'stopped:limits'}, state_obj
assert 'max_commands_per_cycle' in state_obj, state_obj
assert 'max_consecutive_failures' in state_obj, state_obj

print('ok')
PY
