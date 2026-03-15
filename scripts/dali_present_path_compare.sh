#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVIDENCE_ROOT="${ROOT_DIR}/workspace/audit/_evidence"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${1:-${EVIDENCE_ROOT}/cathedral_present_compare_${STAMP}}"
mkdir -p "${OUT_DIR}"

CONTROL="${ROOT_DIR}/tools/cathedralctl"
STATE_PATH="${ROOT_DIR}/workspace/runtime/fishtank_state.json"
CAPTURE_REQUEST_PATH="${ROOT_DIR}/workspace/runtime/fishtank_capture_request.json"

restore_env() {
  systemctl --user set-environment \
    DALI_FISHTANK_SWAP_INTERVAL=1 \
    DALI_FISHTANK_PRESENT_EXPERIMENT=off \
    DALI_FISHTANK_PRESENT_RATE_CAP_OVERRIDE_HZ=0
  systemctl --user unset-environment DALI_FISHTANK_CAPTURE_FILE || true
  rm -f "${CAPTURE_REQUEST_PATH}" || true
}

cleanup() {
  "${CONTROL}" fishtank auto --wait-timeout 20 >/dev/null 2>&1 || true
  restore_env
  systemctl --user restart dali-fishtank.service >/dev/null 2>&1 || true
}
trap cleanup EXIT

capture_case() {
  local name="$1"
  local swap_interval="$2"
  local experiment="$3"
  local rate_cap="$4"
  local case_dir="${OUT_DIR}/${name}"
  mkdir -p "${case_dir}"
  local capture_file="${case_dir}/${name}.framebuffer.png"

  systemctl --user set-environment \
    DALI_FISHTANK_SWAP_INTERVAL="${swap_interval}" \
    DALI_FISHTANK_PRESENT_EXPERIMENT="${experiment}" \
    DALI_FISHTANK_PRESENT_RATE_CAP_OVERRIDE_HZ="${rate_cap}"
  systemctl --user restart dali-fishtank.service >/dev/null
  sleep 2
  "${CONTROL}" fishtank on --wait-visible --wait-timeout 20 >/dev/null
  printf '{\"path\": \"%s\"}\n' "${capture_file}" > "${CAPTURE_REQUEST_PATH}"
  for _ in $(seq 1 12); do
    [[ -f "${capture_file}" ]] && break
    sleep 1
  done

  cp "${STATE_PATH}" "${case_dir}/${name}.state.json"
  if [[ ! -f "${capture_file}" ]]; then
    printf '{\"error\":\"framebuffer_capture_missing\"}\n' > "${case_dir}/${name}.image_stats.json"
    return 0
  fi
  python3 - "${capture_file}" "${case_dir}/${name}.image_stats.json" <<'PY'
from pathlib import Path
import json
import sys
try:
    from PIL import Image
    import numpy as np
except Exception:
    Path(sys.argv[2]).write_text(json.dumps({"error": "missing_pillow_or_numpy"}), encoding="utf-8")
    raise SystemExit(0)
img = Image.open(sys.argv[1]).convert("RGB")
arr = np.asarray(img, dtype=np.uint8)
mean_rgb = arr.reshape((-1, 3)).mean(axis=0)
near_white = ((arr[..., 0] > 245) & (arr[..., 1] > 245) & (arr[..., 2] > 245)).mean()
bright = ((arr[..., 0] > 245) | (arr[..., 1] > 245) | (arr[..., 2] > 245)).mean()
dark = ((arr[..., 0] < 32) & (arr[..., 1] < 32) & (arr[..., 2] < 40)).mean()
Path(sys.argv[2]).write_text(json.dumps({
    "mean_rgb": [float(v) for v in mean_rgb],
    "near_white_ratio": float(near_white),
    "bright_ratio": float(bright),
    "dark_ratio": float(dark),
    "width": int(arr.shape[1]),
    "height": int(arr.shape[0]),
}, indent=2), encoding="utf-8")
PY
}

capture_case "swap1_vsync" "1" "swap1_probe" "0"
capture_case "swap0_uncapped" "0" "swap0_probe" "0"

python3 - "${OUT_DIR}" <<'PY'
from pathlib import Path
import json
import sys
root = Path(sys.argv[1])
summary = {}
for case in ("swap1_vsync", "swap0_uncapped"):
    state = json.loads((root / case / f"{case}.state.json").read_text(encoding="utf-8"))
    summary[case] = {
        "swap_interval": state.get("swap_interval"),
        "present_strategy": state.get("present_strategy"),
        "present_path_diagnosis": state.get("present_path_diagnosis"),
        "renderer_fps": state.get("renderer_fps"),
        "frame_cpu_ms": state.get("frame_cpu_ms"),
        "driver_wait_ms": state.get("driver_wait_ms"),
        "bottleneck_stage": state.get("bottleneck_stage"),
        "stage_timings_avg_ms": state.get("stage_timings_avg_ms"),
    }
(root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
PY
