#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

CURRENT_CRON="${TMP_DIR}/current.cron"
STRIPPED_CRON="${TMP_DIR}/stripped.cron"
NEW_CRON="${TMP_DIR}/new.cron"
BEGIN_TAG="# >>> clawd-ops-managed >>>"
END_TAG="# <<< clawd-ops-managed <<<"

crontab -l >"${CURRENT_CRON}" 2>/dev/null || true

awk -v begin="${BEGIN_TAG}" -v end="${END_TAG}" '
  $0 == begin {skip=1; next}
  $0 == end {skip=0; next}
  !skip {print}
' "${CURRENT_CRON}" >"${STRIPPED_CRON}"

{
  cat "${STRIPPED_CRON}"
  echo "${BEGIN_TAG}"
  echo "OPENCLAW_HOME=${ROOT}"
  echo "17 */3 * * * cd ${ROOT} && bash workspace/scripts/cron_memory_distill.sh"
  echo "15 6 * * * cd ${ROOT} && bash skills/tooling_health/run_daily_tool_validation.sh"
  echo "${END_TAG}"
} >"${NEW_CRON}"

crontab "${NEW_CRON}"
printf 'installed managed cron block (%s)\n' "${NEW_CRON}"
crontab -l
