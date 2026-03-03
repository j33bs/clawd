#!/usr/bin/env bash
if ! (return 0 2>/dev/null); then
  echo "NOTE: run 'source workspace/scripts/quiesce_off.sh' to affect current shell"
fi
unset OPENCLAW_QUIESCE
echo "OPENCLAW_QUIESCE unset (writers enabled)"
