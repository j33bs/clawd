#!/usr/bin/env bash
set -euo pipefail
exec ssh -F /dev/null \
  -o IdentityAgent=none \
  -o IdentitiesOnly=yes \
  -o ControlMaster=no -o ControlPath=none -o ControlPersist=no \
  -o PreferredAuthentications=publickey \
  -o PasswordAuthentication=no \
  -i "${HOME}/.ssh/id_ed25519" \
  "jeebs@100.113.160.1" "$@"
