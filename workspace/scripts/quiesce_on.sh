#!/usr/bin/env bash
if ! (return 0 2>/dev/null); then
  echo "NOTE: run 'source workspace/scripts/quiesce_on.sh' to affect current shell"
fi
export OPENCLAW_QUIESCE=1
echo "OPENCLAW_QUIESCE=1 (writers disabled)"
