#!/usr/bin/env bash
set -euo pipefail

command="${1:-run}"

case "$command" in
  run)
    printf '%s\n' \
      'openclaw-dali-heavy-node.service is a deprecated compatibility lane.' \
      'No heavy cognition runtime is installed on this host.' >&2
    exit 64
    ;;
  *)
    echo "usage: $0 run" >&2
    exit 2
    ;;
esac
