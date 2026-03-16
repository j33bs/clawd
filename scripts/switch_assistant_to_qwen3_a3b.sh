#!/usr/bin/env bash
set -euo pipefail

MODEL_REPO="cyankiwi/Qwen3-30B-A3B-Instruct-2507-AWQ-4bit"
MODEL_DIR="/opt/models/qwen3_30b_a3b_instruct_2507_awq_4bit_cyankiwi"
ENV_FILE="$HOME/.config/openclaw/vllm-assistant.env"
LOG_PATH="${1:-$HOME/.local/state/openclaw/qwen3-a3b-switch.log}"

mkdir -p "$(dirname "$LOG_PATH")"
mkdir -p "$MODEL_DIR"

log() {
  printf '[%s] %s\n' "$(date '+%F %T')" "$*" | tee -a "$LOG_PATH"
}

download_file() {
  local name="$1"
  local url="https://huggingface.co/${MODEL_REPO}/resolve/main/${name}?download=true"
  log "download start file=${name}"
  wget \
    --inet4-only \
    --continue \
    --tries=0 \
    --retry-connrefused \
    --waitretry=5 \
    --timeout=30 \
    --read-timeout=30 \
    --output-document="${MODEL_DIR}/${name}" \
    "$url" >>"$LOG_PATH" 2>&1
  log "download done file=${name}"
}

write_env() {
  cat >"$ENV_FILE" <<'EOF'
OPENCLAW_VLLM_ASSISTANT_PORT=8001
OPENCLAW_VLLM_ASSISTANT_GPU_MEMORY_UTILIZATION=0.90
OPENCLAW_VLLM_ASSISTANT_MODEL_PATH=/opt/models/qwen3_30b_a3b_instruct_2507_awq_4bit_cyankiwi
OPENCLAW_VLLM_ASSISTANT_QUANTIZATION=compressed-tensors
OPENCLAW_VLLM_ASSISTANT_MAX_MODEL_LEN=8192
OPENCLAW_VLLM_ASSISTANT_MAX_NUM_SEQS=4
EOF
  log "wrote assistant env file=${ENV_FILE}"
}

verify_model_dir() {
  local missing=0
  local file
  for file in \
    config.json \
    generation_config.json \
    tokenizer.json \
    tokenizer_config.json \
    special_tokens_map.json \
    chat_template.jinja \
    merges.txt \
    vocab.json \
    added_tokens.json \
    recipe.yaml \
    model.safetensors.index.json \
    model-00001-of-00004.safetensors \
    model-00002-of-00004.safetensors \
    model-00003-of-00004.safetensors \
    model-00004-of-00004.safetensors; do
    if [[ ! -s "${MODEL_DIR}/${file}" ]]; then
      log "missing file=${file}"
      missing=1
    fi
  done
  return "$missing"
}

restart_and_verify() {
  log "restarting openclaw-vllm.service"
  systemctl --user restart openclaw-vllm.service
  local deadline=$((SECONDS + 300))
  while (( SECONDS < deadline )); do
    if curl -fsS http://127.0.0.1:8001/v1/models >/tmp/qwen3_assistant_models.json 2>/dev/null; then
      log "assistant lane healthy"
      cat /tmp/qwen3_assistant_models.json | tee -a "$LOG_PATH"
      rm -f /tmp/qwen3_assistant_models.json
      return 0
    fi
    sleep 5
  done
  log "assistant lane verification timed out"
  systemctl --user --no-pager --full status openclaw-vllm.service >>"$LOG_PATH" 2>&1 || true
  return 1
}

log "switch start model_repo=${MODEL_REPO}"

for file in \
  .gitattributes \
  README.md \
  added_tokens.json \
  chat_template.jinja \
  config.json \
  generation_config.json \
  merges.txt \
  model-00001-of-00004.safetensors \
  model-00002-of-00004.safetensors \
  model-00003-of-00004.safetensors \
  model-00004-of-00004.safetensors \
  model.safetensors.index.json \
  recipe.yaml \
  special_tokens_map.json \
  tokenizer.json \
  tokenizer_config.json \
  vocab.json; do
  download_file "$file"
done

verify_model_dir
write_env
restart_and_verify
log "switch complete"
