# OpenClaw Skills Setup (Requested Set)

Date: 2026-02-06

## Scope
Skills covered:
- peakaboo (workspace alias for `peekaboo`)
- summarize
- tmux
- bird
- himalaya
- local-places
- model-usage
- openai-whisper

## Prerequisites

### macOS
Run:

```bash
scripts/install_requested_skills.sh
scripts/wire_skills_to_openclaw.sh
```

### Ubuntu/Debian
Run/install baseline (documented path):

```bash
sudo apt-get update
sudo apt-get install -y tmux python3 python3-pip python3-venv curl ca-certificates npm
curl -LsSf https://astral.sh/uv/install.sh | sh
python3 -m pip install --user -U openai-whisper
sudo npm install -g @steipete/bird
```

Then wire repository skills into OpenClaw config:

```bash
scripts/wire_skills_to_openclaw.sh
```

Notes:
- `peekaboo` is macOS-only.
- `model-usage` relies on `codexbar` (macOS-first tooling).
- `summarize` and `himalaya` may require manual installation on Linux depending on distro packages.

## Verification
Single command:

```bash
scripts/verify_skills.sh
```

Artifact path used in this rollout:
- `notes/verification/2026-02-06-skills-verify.txt`

## Skill Sections

### peakaboo
- Purpose: compatibility alias so users can invoke Peekaboo using `peakaboo` naming.
- Usage example:
  - `openclaw skills info peakaboo`
  - `peekaboo --help`
- Failure modes:
  - Missing `peekaboo` binary.
  - macOS privacy permissions not granted for screen automation.

### summarize
- Purpose: summarize URLs/files/videos.
- Usage example:
  - `summarize "https://example.com" --length short`
- Failure modes:
  - Missing `summarize` binary.
  - Provider API key not set for requested model backend.

### tmux
- Purpose: controlled interactive session execution.
- Usage example:
  - `tmux -V`
  - `tmux -S /tmp/openclaw.sock new -d -s smoke`
- Failure modes:
  - Missing `tmux` binary.
  - Socket/session permission conflicts.

### bird
- Purpose: X/Twitter CLI operations.
- Usage example:
  - `bird --help`
  - `bird whoami`
- Failure modes:
  - Missing `bird` binary.
  - Missing/invalid auth cookies.

### himalaya
- Purpose: terminal email access.
- Usage example:
  - `himalaya --help`
  - `himalaya account list`
- Failure modes:
  - Missing `himalaya` binary.
  - Missing `~/.config/himalaya/config.toml` or invalid account credentials.

### local-places
- Purpose: local Places proxy flow.
- Usage example:
  - `uv --version`
  - run API server from `skills/local-places` with `GOOGLE_PLACES_API_KEY`.
- Failure modes:
  - Missing `uv` binary.
  - Missing/invalid `GOOGLE_PLACES_API_KEY` for live search.

### model-usage
- Purpose: summarize per-model usage from CodexBar cost output.
- Usage example:
  - `python3 skills/model-usage/scripts/model_usage.py --provider codex --mode all`
- Failure modes:
  - Missing `codexbar` binary.
  - CodexBar cost dataset unavailable.

### openai-whisper
- Purpose: local speech-to-text using Whisper CLI.
- Usage example:
  - `whisper /path/to/audio.m4a --model turbo --output_format txt`
- Failure modes:
  - Missing `whisper` binary.
  - Runtime/model-cache issues on first model download.

