# Design Brief: OpenClaw Skill Enablement (Step B)

Date: 2026-02-06

## Goal
Enable these skills for agent use in OpenClaw with auditable, reversible repo changes:
- peakaboo (implemented as `peekaboo` alias)
- summarize
- tmux
- bird
- himalaya
- local-places
- model-usage
- openai-whisper

## Skill-by-skill plan

### 1) peakaboo (peekaboo)
- Purpose: macOS UI inspection/automation skill.
- External dependencies:
  - macOS: `peekaboo` (brew formula `steipete/tap/peekaboo`).
  - Ubuntu/Debian: not supported by upstream skill metadata (`darwin` only).
- Implementation approach:
  - Add repo adapter alias `peakaboo -> peekaboo` for verification and operator commands.
  - Rely on bundled OpenClaw `peekaboo` skill implementation.
- Registration/invocation:
  - OpenClaw already registers bundled `peekaboo`; readiness is binary-gated.

### 2) summarize
- Purpose: summarize URLs/files/video links.
- External dependencies:
  - macOS: `summarize` via brew.
  - Ubuntu/Debian: install summarize CLI from upstream toolchain (documented fallback).
- Implementation approach:
  - Adapter wrapper to run smoke checks without model/API cost.
- Registration/invocation:
  - Bundled skill, enabled by presence of `summarize` binary.

### 3) tmux
- Purpose: controlled interactive CLI session management.
- External dependencies:
  - macOS: `tmux` via brew.
  - Ubuntu/Debian: `apt install tmux`.
- Implementation approach:
  - Wrapper that validates session create/capture/teardown on isolated socket.
- Registration/invocation:
  - Bundled skill, enabled by `tmux` binary.

### 4) bird
- Purpose: lightweight X/Twitter data interactions.
- External dependencies:
  - macOS: `bird` via brew or npm (`@steipete/bird`).
  - Ubuntu/Debian: npm install path.
- Implementation approach:
  - Dependency check only in smoke mode (no auth-required posting).
- Registration/invocation:
  - Bundled skill, enabled by `bird` binary.

### 5) himalaya
- Purpose: terminal email operations.
- External dependencies:
  - macOS: `himalaya` via brew.
  - Ubuntu/Debian: `apt install himalaya` (or release binary), plus account config.
- Implementation approach:
  - Smoke checks limited to version/config presence (no mailbox mutations).
- Registration/invocation:
  - Bundled skill, enabled by `himalaya` binary.

### 6) local-places
- Purpose: local Google Places proxy workflow.
- External dependencies:
  - macOS: `uv` + `GOOGLE_PLACES_API_KEY`.
  - Ubuntu/Debian: `uv` + `GOOGLE_PLACES_API_KEY`.
- Implementation approach:
  - Repo adapter script to validate env/bin and optional local ping flow.
  - No silent network calls; API dependency documented.
- Registration/invocation:
  - Bundled skill, enabled by `uv` and required env key.

### 7) model-usage
- Purpose: model cost/usage summaries from CodexBar output.
- External dependencies:
  - macOS: `codexbar` (brew cask).
  - Ubuntu/Debian: unsupported by current upstream skill metadata; document as macOS-only.
- Implementation approach:
  - Adapter that runs bundled `model_usage.py` in local/sample mode when possible.
- Registration/invocation:
  - Bundled skill, enabled by `codexbar` binary.

### 8) openai-whisper
- Purpose: local speech-to-text.
- External dependencies:
  - macOS: `whisper` (`openai-whisper` formula).
  - Ubuntu/Debian: install whisper CLI via pip package path.
- Implementation approach:
  - Smoke verification on CLI availability + help/version.
- Registration/invocation:
  - Bundled skill, enabled by `whisper` binary.

## Common interface (repo adapters)
All repo adapters will follow:
- Input:
  - `--check` (dependency-only)
  - `--smoke` (minimal invocation, no destructive writes)
  - `--json` (machine-readable status)
- Output JSON shape:
  - `{ skill, alias?, ready, checks: [{name, pass, detail}], guidance: [] }`
- Error shape:
  - non-zero exit on hard failure
  - structured failure reason in JSON and stderr

## Registration and wiring strategy
1. Keep bundled skills as source of truth (no fork of upstream SKILL.md required).
2. Add workspace-level alias shim for `peakaboo` naming mismatch.
3. Add auditable scripts to:
   - install/document dependencies by OS
   - run per-skill smoke checks
   - verify OpenClaw sees all 8 as eligible (`openclaw skills check` + info checks).

## Verification strategy
- Single command: `scripts/verify_skills.sh`
- Responsibilities:
  1. Validate required binaries/env/config per skill.
  2. Execute minimal smoke checks (safe/read-only where possible).
  3. Validate OpenClaw readiness for target skills.
  4. Return clear pass/fail summary and non-zero status on failure.

## Cross-platform considerations
- macOS is primary execution target for all requested skills.
- Linux support matrix:
  - supported with documented install path: `summarize`, `tmux`, `bird`, `himalaya`, `local-places`, `openai-whisper`
  - limited/macOS-only: `peekaboo`, `model-usage` (CodexBar dependency)
- Docs will explicitly separate macOS vs Ubuntu/Debian prerequisites.

