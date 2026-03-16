#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$HOME/.config/openclaw/vllm-assistant.env"
LOG_PATH="${1:-$HOME/.local/state/openclaw/qwen35-27b-gguf-llamacpp-switch.log}"
MODEL_REPO="bartowski/Qwen_Qwen3.5-27B-GGUF"
MODEL_FILE="Qwen_Qwen3.5-27B-Q4_K_M.gguf"
MODEL_DIR="/opt/models/qwen35_27b_gguf"
MODEL_PATH="${MODEL_DIR}/${MODEL_FILE}"
LLAMACPP_ROOT="${ROOT_DIR}/.runtime/llama.cpp-vulkan"
LLAMACPP_TARBALL="${ROOT_DIR}/.runtime/llama-b8252-bin-ubuntu-vulkan-x64.tar.gz"
LLAMACPP_RELEASE_URL="https://github.com/ggml-org/llama.cpp/releases/download/b8252/llama-b8252-bin-ubuntu-vulkan-x64.tar.gz"
EXPECTED_MODEL_BYTES="17128621600"

mkdir -p "$(dirname "$LOG_PATH")"
mkdir -p "$MODEL_DIR"
mkdir -p "$ROOT_DIR/.runtime"

log() {
  printf '[%s] %s\n' "$(date '+%F %T')" "$*" | tee -a "$LOG_PATH"
}

download_file() {
  local url="$1"
  local out="$2"
  log "download start url=${url} out=${out}"
  wget \
    --inet4-only \
    --continue \
    --tries=0 \
    --retry-connrefused \
    --waitretry=5 \
    --timeout=30 \
    --read-timeout=30 \
    --output-document="$out" \
    "$url" >>"$LOG_PATH" 2>&1
  log "download done out=${out}"
}

install_llamacpp() {
  if [[ -x "$LLAMACPP_ROOT/bin/llama-server" ]]; then
    log "llama.cpp already present root=${LLAMACPP_ROOT}"
    return 0
  fi
  download_file "$LLAMACPP_RELEASE_URL" "$LLAMACPP_TARBALL"
  rm -rf "$LLAMACPP_ROOT"
  mkdir -p "$LLAMACPP_ROOT"
  tar -xzf "$LLAMACPP_TARBALL" -C "$LLAMACPP_ROOT" --strip-components=1
  chmod +x "$LLAMACPP_ROOT/llama-server"
  log "llama.cpp installed root=${LLAMACPP_ROOT}"
}

install_model() {
  if [[ -f "$MODEL_PATH" ]]; then
    local current_size
    current_size="$(stat -c '%s' "$MODEL_PATH" 2>/dev/null || echo 0)"
    if [[ "$current_size" == "$EXPECTED_MODEL_BYTES" ]]; then
      log "model already present path=${MODEL_PATH} bytes=${current_size}"
      return 0
    fi
    log "model partial path=${MODEL_PATH} bytes=${current_size} expected=${EXPECTED_MODEL_BYTES}"
  fi
  download_file \
    "https://huggingface.co/${MODEL_REPO}/resolve/main/${MODEL_FILE}?download=true" \
    "$MODEL_PATH"
  local final_size
  final_size="$(stat -c '%s' "$MODEL_PATH" 2>/dev/null || echo 0)"
  if [[ "$final_size" != "$EXPECTED_MODEL_BYTES" ]]; then
    log "model size mismatch path=${MODEL_PATH} bytes=${final_size} expected=${EXPECTED_MODEL_BYTES}"
    return 1
  fi
}

write_env() {
  cat >"$ENV_FILE" <<EOF
OPENCLAW_ASSISTANT_RUNTIME=llamacpp
OPENCLAW_VLLM_ASSISTANT_HOST=0.0.0.0
OPENCLAW_VLLM_ASSISTANT_PORT=8001
OPENCLAW_VLLM_ASSISTANT_SERVED_MODEL_NAME=local-assistant
OPENCLAW_ASSISTANT_MODEL_PATH=${MODEL_PATH}
OPENCLAW_ASSISTANT_CTX_SIZE=16384
OPENCLAW_ASSISTANT_N_GPU_LAYERS=999
OPENCLAW_ASSISTANT_CACHE_TYPE_K=q8_0
OPENCLAW_ASSISTANT_CACHE_TYPE_V=q8_0
OPENCLAW_LLAMACPP_ROOT=${LLAMACPP_ROOT}
OPENCLAW_LLAMACPP_SERVER_BIN=${LLAMACPP_ROOT}/llama-server
EOF
  log "wrote assistant env file=${ENV_FILE}"
}

restart_and_verify() {
  log "daemon-reload + restart openclaw-vllm.service"
  systemctl --user daemon-reload
  systemctl --user restart openclaw-vllm.service
  local deadline=$((SECONDS + 300))
  while (( SECONDS < deadline )); do
    if curl -fsS http://127.0.0.1:8001/v1/models >/tmp/qwen35_llamacpp_models.json 2>/dev/null; then
      log "assistant lane healthy"
      cat /tmp/qwen35_llamacpp_models.json | tee -a "$LOG_PATH"
      rm -f /tmp/qwen35_llamacpp_models.json
      return 0
    fi
    sleep 5
  done
  log "assistant lane verification timed out"
  systemctl --user --no-pager --full status openclaw-vllm.service >>"$LOG_PATH" 2>&1 || true
  return 1
}

log "switch start runtime=llamacpp model_repo=${MODEL_REPO} model_file=${MODEL_FILE}"
install_llamacpp
install_model
write_env
restart_and_verify
log "switch complete"
