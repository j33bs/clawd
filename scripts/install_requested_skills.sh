#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[install-skills] %s\n' "$*"
}

has() {
  command -v "$1" >/dev/null 2>&1
}

install_brew_formula() {
  local formula="$1"
  local cmd_name="$2"
  if brew list --formula "$formula" >/dev/null 2>&1; then
    log "brew formula already installed: $formula"
  else
    log "installing brew formula: $formula"
    if ! brew install "$formula"; then
      if has "$cmd_name"; then
        log "install command returned non-zero but binary is available: $cmd_name"
      else
        return 1
      fi
    fi
  fi
}

install_brew_cask() {
  local cask="$1"
  if brew list --cask "$cask" >/dev/null 2>&1; then
    log "brew cask already installed: $cask"
  else
    log "installing brew cask: $cask"
    brew install --cask "$cask"
  fi
}

install_macos() {
  if ! has brew; then
    log "Homebrew is required on macOS. Install from https://brew.sh"
    exit 1
  fi

  log "ensuring steipete tap is available"
  brew tap steipete/tap

  install_brew_formula steipete/tap/peekaboo peekaboo
  install_brew_formula steipete/tap/summarize summarize
  install_brew_formula tmux tmux
  install_brew_formula steipete/tap/bird bird
  install_brew_formula himalaya himalaya
  install_brew_formula uv uv
  install_brew_formula openai-whisper whisper
  install_brew_cask steipete/tap/codexbar

  log "macOS dependencies installed"
  log "local-places still requires GOOGLE_PLACES_API_KEY"
}

install_linux() {
  log "installing Ubuntu/Debian baseline dependencies"
  if ! has apt-get; then
    log "This Linux installer currently supports apt-based systems only"
    exit 1
  fi

  sudo apt-get update
  sudo apt-get install -y tmux python3 python3-pip python3-venv curl ca-certificates npm

  if ! has uv; then
    log "installing uv"
    curl -LsSf https://astral.sh/uv/install.sh | sh
  fi

  if ! has whisper; then
    log "installing openai-whisper via pip"
    python3 -m pip install --user -U openai-whisper
  fi

  if ! has bird; then
    log "installing bird via npm"
    sudo npm install -g @steipete/bird
  fi

  if ! has himalaya; then
    log "himalaya binary not found after apt install; install manually from https://github.com/pimalaya/himalaya"
  fi

  if ! has summarize; then
    log "summarize binary not found; install manually from https://summarize.sh"
  fi

  if ! has codexbar; then
    log "model-usage dependency codexbar is currently macOS-first; mark as unsupported on Linux"
  fi

  log "Linux dependencies completed"
  log "local-places still requires GOOGLE_PLACES_API_KEY"
}

main() {
  local os
  os="$(uname -s)"

  case "$os" in
    Darwin)
      install_macos
      ;;
    Linux)
      install_linux
      ;;
    *)
      log "Unsupported OS: $os"
      exit 1
      ;;
  esac
}

main "$@"
