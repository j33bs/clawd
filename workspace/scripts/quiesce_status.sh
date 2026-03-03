#!/usr/bin/env bash

if [[ "${OPENCLAW_QUIESCE:-}" == "1" ]]; then
  echo "OPENCLAW_QUIESCE=1 (writers disabled)"
else
  echo "OPENCLAW_QUIESCE is unset or !=1 (writers enabled)"
fi

echo "Protected paths:"
echo "- workspace/state/tacti_cr/events.jsonl"
echo "- workspace/research/findings.json"
echo "- workspace/research/queue.json"
echo "- workspace/research/wander_log.md"
