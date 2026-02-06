# Design Note: Skills Install Discovery (Step A)

Date: 2026-02-06

## Scope
Discovery-only checkpoint for installing and wiring these OpenClaw skills:
- peakaboo (mapped to bundled skill name `peekaboo`)
- summarize
- tmux
- bird
- himalaya
- local-places
- model-usage
- openai-whisper

No implementation changes in this step.

## 1) Current Skill Architecture

### Where skills live
OpenClaw loads skills from three locations (highest precedence first):
1. `<workspace>/skills`
2. `~/.openclaw/skills`
3. Bundled package skills (current install): `~/.npm-global/lib/node_modules/openclaw/skills`

### How skills are registered
- Registration is filesystem-driven by presence of `SKILL.md` in a skill directory.
- Skill metadata frontmatter uses `metadata.openclaw` with gates such as:
  - `requires.bins`
  - `requires.env`
  - `requires.config`
  - `os`
  - optional installer hints (`install`).
- OpenClaw config path for overrides: `~/.openclaw/openclaw.json` under `skills.*`.

### How agents invoke skills
- Eligible skills are injected into prompt context.
- Agent reads and follows `SKILL.md` instructions when a skill matches intent.
- Current runtime visibility checked via:
  - `openclaw skills list`
  - `openclaw skills info <skill>`
  - `openclaw skills check`

### Existing requested skill availability
All requested skills exist as bundled skills in the local OpenClaw install; readiness depends on requirements:
- `peekaboo` (requested as peakaboo): missing `peekaboo` bin
- `summarize`: missing `summarize` bin
- `tmux`: missing `tmux` bin
- `bird`: missing `bird` bin
- `himalaya`: missing `himalaya` bin
- `local-places`: missing `uv` bin and `GOOGLE_PLACES_API_KEY`
- `model-usage`: missing `codexbar` bin
- `openai-whisper`: missing `whisper` bin

## 2) Dependency Management Approach
Observed from bundled skill metadata and docs:
- Package managers used by skills:
  - macOS: primarily `brew`
  - Linux: typically apt + tool-specific install path (where available)
  - Python tools: `uv` / pip-backed flow
  - Node tools: npm-based install for some skills (e.g., bird alternative)
- Install hints are declared per skill in `SKILL.md` metadata.

## 3) Verification/Test Patterns
- OpenClaw-native checks:
  - `openclaw skills check` (readiness gate)
  - `openclaw skills info <name>` (requirement details)
- Repo-local pattern: utility scripts under `/Users/heathyeager/clawd/scripts` with lightweight check scripts (e.g., `*_check.js`).
- No existing single skill-suite verifier for the requested 8 skills.

## 4) Documentation Conventions
Repo documentation style is concise Markdown notes, typically:
- title + date
- short sections (`What/Why/Constraints/Scope` or equivalent)
- minimal formatting churn

## 5) Governance/Gate Context
- No explicit `Run-007` marker found in this repo.
- Current equivalent governance constraints are represented by workspace constitutional docs (`SOUL.md`, `AGENTS.md`) and OpenClaw skills gating (`openclaw skills check`).
- Implementation plan will preserve reversibility by creating file backups before edits and using small auditable commits.

