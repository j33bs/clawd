# Discord Project Bridge

Date: 2026-03-10

## Purpose

Expose canonical Dali project/runtime state to Discord without making Discord the source of truth.

Canonical state remains local:

- `workspace/source-ui/config/projects.json`
- `workspace/source-ui/state/tasks.json`
- `sim/SIM_*/performance.json`
- `~/.local/state/openclaw/*.log`
- `workspace/teamchat/state/*.json`

Discord is downstream:

- status fanout
- project intake summaries
- sim alerts
- discussion threads rooted in task IDs

## Local Preview Flow

Bridge config:

- `workspace/source-ui/config/discord_bridge.json`

Render a preview to stdout:

```bash
python3 workspace/scripts/discord_project_bridge.py preview
```

Render and persist the current preview/status:

```bash
python3 workspace/scripts/discord_project_bridge.py render-status
```

Rendered status file:

- `workspace/source-ui/state/discord_bridge_status.json`

## Webhook Wiring

Each channel config references an environment variable, not a literal webhook URL:

- `OPENCLAW_DISCORD_OPS_WEBHOOK`
- `OPENCLAW_DISCORD_SIM_WEBHOOK`
- `OPENCLAW_DISCORD_PROJECT_WEBHOOK`

This keeps secrets out of the repo and lets Source UI show whether a channel is configured without exposing the secret.

## Delivery Model

Recommended channel layout:

- `#ops-status`
- `#sim-watch`
- `#project-intake`

Recommended Discord usage:

- webhooks for one-way alert fanout
- slash commands for task/status interactions
- per-task threads for discussion

The current implementation covers local rendering and webhook fanout only. It does not register slash commands or send anything unless an operator explicitly invokes:

```bash
python3 workspace/scripts/discord_project_bridge.py post-webhooks
```

## Safety

- Discord is not the task database.
- Source UI/task JSON remains canonical.
- Preview mode stays useful even with no webhook env vars present.
- Messages are rendered in short bullet form for Discord-safe formatting.
