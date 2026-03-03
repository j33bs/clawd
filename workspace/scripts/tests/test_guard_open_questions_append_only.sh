#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
GUARD="$REPO_ROOT/workspace/scripts/hooks/guard_open_questions_append_only.sh"

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
cd "$workdir"

git init -q
mkdir -p workspace/scripts/hooks
cat > workspace/OPEN_QUESTIONS.md <<'MD'
# Open Questions

1. First question
MD

git add workspace/OPEN_QUESTIONS.md
git -c user.name=t -c user.email=t@t commit -q -m init

# Append should pass.
printf '\n2. Second question\n' >> workspace/OPEN_QUESTIONS.md
git add workspace/OPEN_QUESTIONS.md
bash "$GUARD"
git restore --staged workspace/OPEN_QUESTIONS.md
git checkout -- workspace/OPEN_QUESTIONS.md

# Mutation should fail.
python3 - <<'PY'
from pathlib import Path
p = Path('workspace/OPEN_QUESTIONS.md')
p.write_text('# Open Questions\n\n1. Mutated first question\n', encoding='utf-8')
PY
git add workspace/OPEN_QUESTIONS.md
if bash "$GUARD"; then
  echo "expected guard to fail on mutation" >&2
  exit 1
fi

# Bypass should pass.
OPENCLAW_GOV_BYPASS=1 bash "$GUARD"
