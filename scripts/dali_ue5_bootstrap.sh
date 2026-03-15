#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/jeebs/src/clawd"
UE_ROOT="${ROOT}/.runtime/UnrealEngine-5.6"
PROJECT="${ROOT}/workspace/dali_unreal/DaliMirror.uproject"
LOG_DIR="${ROOT}/.runtime/logs"
GEN_LOG="${LOG_DIR}/ue5-generate.log"
BUILD_LOG="${LOG_DIR}/ue5-build.log"

mkdir -p "${LOG_DIR}"

if [[ ! -d "${UE_ROOT}" ]]; then
  echo "UE source tree missing: ${UE_ROOT}" >&2
  exit 1
fi

if [[ ! -f "${PROJECT}" ]]; then
  echo "UE project missing: ${PROJECT}" >&2
  exit 1
fi

if systemctl --user is-active --quiet dali-ue5-setup.service; then
  echo "Setup is still running: dali-ue5-setup.service" >&2
  exit 2
fi

echo "[1/2] Generating project files..."
(
  cd "${UE_ROOT}"
  bash ./GenerateProjectFiles.sh -project="${PROJECT}" -game -engine
) |& tee "${GEN_LOG}"

echo "[2/2] Building DaliMirrorEditor..."
(
  cd "${UE_ROOT}"
  bash ./Engine/Build/BatchFiles/Linux/Build.sh DaliMirrorEditor Linux Development "${PROJECT}" -progress
) |& tee "${BUILD_LOG}"

echo "UE5 bootstrap completed."
echo "Generate log: ${GEN_LOG}"
echo "Build log: ${BUILD_LOG}"
