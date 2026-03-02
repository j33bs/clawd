#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
EVDIR="workspace/audit/_evidence/post_merge_verify_${TS}"
mkdir -p "$EVDIR"

exec > >(tee -a "$EVDIR/run.log") 2>&1

echo "== POST-MERGE VERIFY =="
echo "ts=${TS}"
echo "repo=$ROOT"

echo "== 1) Git Context =="
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git status --porcelain=v1 || true

echo "== 2) Service Status =="
systemctl --user status openclaw-gateway.service openclaw-heavy-worker.timer --no-pager || true

echo "== 3) Policy File Check =="
POLICY="workspace/governance/policy/contract_thresholds.json"
if [ -r "$POLICY" ]; then
  echo "policy_file=ok path=$POLICY"
  sed -n '1,120p' "$POLICY"
else
  echo "policy_file=missing_or_unreadable path=$POLICY"
fi

echo "== 4) Contract Tick Snapshot =="
python3 workspace/scripts/contractctl.py tick || true
python3 - <<'PY'
import json
from pathlib import Path
p = Path('workspace/state_runtime/contract/current.json')
if not p.exists():
    print('current_json=missing')
    raise SystemExit(0)
cur = json.loads(p.read_text(encoding='utf-8'))
out = {
  'mode': cur.get('mode'),
  'source': cur.get('source'),
  'idle': (cur.get('service_load') or {}).get('idle'),
  'ewma_rate': (cur.get('service_load') or {}).get('ewma_rate'),
  'queue_depth': cur.get('queue_depth'),
  'policy_source': cur.get('policy_source'),
}
print(json.dumps(out, indent=2, sort_keys=True))
PY

echo "== 5) Enqueue + CODE override + worker run =="
mkdir -p workspace/state_runtime/queue/runs
BEFORE_COUNT="$(find workspace/state_runtime/queue/runs -name result.json 2>/dev/null | wc -l | tr -d ' ')"
echo "runs_before=${BEFORE_COUNT}"
python3 workspace/scripts/heavy_queue.py enqueue --cmd "bash -lc 'echo heavy && sleep 1'" --kind HEAVY_CODE --priority 50 --ttl-minutes 30
python3 workspace/scripts/contractctl.py set-mode CODE --ttl 5m --reason 'post_merge_verify'
python3 workspace/scripts/heavy_worker.py || true
AFTER_COUNT="$(find workspace/state_runtime/queue/runs -name result.json 2>/dev/null | wc -l | tr -d ' ')"
echo "runs_after=${AFTER_COUNT}"
if [ "$AFTER_COUNT" -gt "$BEFORE_COUNT" ]; then
  echo "run_artifact=created"
else
  echo "run_artifact=not_detected"
fi

echo "== events tail =="
tail -n 40 workspace/state_runtime/contract/events.jsonl || true

echo "== 6) Idle Reaper Status =="
systemctl --user status openclaw-idle-reaper.timer openclaw-idle-reaper.service --no-pager || true

echo "== cleanup override =="
python3 workspace/scripts/contractctl.py clear-override || true

echo "evidence_dir=${EVDIR}"
