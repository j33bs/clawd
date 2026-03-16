# Dashboard + Discord Project Hub

Date: 2026-03-10

## Goal

Build a single operational surface that shows:

- all active projects
- sim performance and risk state
- current runtime work
- Discord-linked project management and system communication

without making Discord the source of truth.

## What Exists Already

- `workspace/source-ui/` is the best starting point for a control-plane dashboard.
- `sim/SIM_*/performance.json` and `sim/SIM_*/state.json` already expose live trading outputs.
- `~/.local/state/openclaw/itc-cycle.log` shows live ITC pipeline activity.
- `workspace/runtime/phase1_idle_status.json` exposes DALI Phase One activity.
- `workspace/local_exec/state/jobs.jsonl` is the right shape for governed background work.
- `workspace/source-ui/state/tasks.json` now acts as the local task board source of truth for Source UI.
- `workspace/teamchat/state/*.json` and `workspace/teamchat/sessions/*.jsonl` provide the in-system communication layer.
- `workspace/source-ui/config/discord_bridge.json` + `workspace/scripts/discord_project_bridge.py` provide a local-first Discord bridge preview/fanout path.

## Recommended Architecture

### 1. One canonical state model

The dashboard should read from a repo-native backend payload, not from UI-local demo state and not from Discord message history.

Canonical sources:

- project inventory: `workspace/source-ui/config/projects.json`
- optional external signal inventory: `workspace/source-ui/config/external_signals.json`
- project/task system of record: GitHub Projects or a repo-native JSON/JSONL ledger
- runtime work: `workspace/local_exec/state/jobs.jsonl`
- sim telemetry: `sim/SIM_*/performance.json`, `sim/SIM_*/state.json`
- service health: systemd user units
- operator activity/log signals: `~/.local/state/openclaw/*.log`

### 2. Discord is a control and collaboration surface

Discord should sit on top of canonical state:

- create task
- move task
- ask status
- subscribe to alerts
- open threaded discussion for a task or incident

Discord should not be the only place where task truth lives.

### 3. Event-driven updates, polled fallback

Use push where possible:

- dashboard: SSE or WebSocket for live updates
- Discord: slash commands + interaction callbacks + webhooks for alerts

Use polling only for legacy file-backed sources that do not emit events yet.

### 4. Structured channel model

Recommended Discord layout:

- `#ops-status`
  system alerts, deploy state, service health
- `#project-intake`
  create new work, triage, slash-command initiated
- `#sim-watch`
  sim snapshots, drawdown alerts, halts
- `#dali-phase-one`
  generation jobs, audit drops, review loops
- per-project threads
  scoped discussion attached to a task or incident

This keeps broadcast channels clean and uses threads for local context.

### 5. Tight permissions and low-intent footprint

Prefer:

- slash commands
- webhooks
- interaction endpoints

Avoid relying on broad message scraping unless you truly need it. This lowers moderation risk and reduces privileged-intent dependency.

### 6. Explicit automation boundaries

Every Discord-triggered action should declare:

- actor
- intent
- target project/task
- allowed tool scope
- audit trail

This is especially important for anything that can restart services, enqueue jobs, or modify project state.

### 7. Optional external sentiment feed

Add a polled JSON sentiment file produced on the MacBook M2 as a non-required input.

Rules:

- the 3090 stack may poll the JSON file when available
- the feed must be surfaced in the dashboard as optional external state
- `model.resolved` is the authoritative model label for explainability and dashboard display
- trading must fail open if the laptop or feed goes offline
- when the feed is missing or stale, the 3090 lane falls back to dynamic weighting from local inference only
- feed freshness should be visible, but absence should not halt execution
- incoming source scores remain input-only; combined weighting/bias is computed and exposed on the Dali side only

## Contemporary Best Practices

### Dashboard / observability

- Use one schema for metrics, logs, and work items, even if data initially comes from files.
- Treat OpenTelemetry-style normalization as the long-term target so the dashboard is not tied forever to bespoke log parsing.
- Keep operator dashboards action-oriented: state, risk, current work, and next intervention.
- Separate summary cards from drill-down data. The top level should answer "what needs attention now?"

### Project management

- Use a structured board with explicit fields: project, owner, status, priority, risk, due date, link to evidence.
- Keep discussion linked to tasks, not free-floating.
- Automate status transitions from runtime events where possible, but require human confirmation for high-impact closes.

### Discord integration

- Use slash commands for task creation, assignment, and status reads.
- Use webhooks for one-way alert fanout.
- Use threads for per-task discussion and incident handling.
- Keep responses short and link back to the dashboard/task URL for detail.
- Use role-based command access for operational commands.

## Recommended Phases

### Phase 1: canonical dashboard

- replace demo dashboard data with repo-native payloads
- show projects, sims, and current work
- keep task board simple

### Phase 2: real project system

- choose canonical task backend:
  - GitHub Projects if you want durable issue/PR linkage and multi-device access
  - repo-native JSONL if you want local-first control and lower external dependency
- add task IDs, owners, status, evidence links

### Phase 3: Discord bridge

- add slash commands:
  - `/task create`
  - `/task move`
  - `/project status`
  - `/sim status`
  - `/ops health`
- add alert webhooks to `#ops-status` and `#sim-watch`
- create per-task threads from command handlers

### Phase 4: live transport

- move dashboard refresh from polling to SSE/WebSocket
- emit state changes from local_exec, sim runner, and service watchers
- attach audit IDs to user-visible events

## Repo-Specific Recommendation

Best fit here:

1. Keep `workspace/source-ui` as the main dashboard.
2. Use `workspace/source-ui/config/projects.json` as the starter project inventory.
3. Make GitHub Projects the long-term task system of record if you want PR/issues and external access.
4. Use Discord for:
   - intake
   - status queries
   - alerts
   - thread-based discussion
5. Keep all execution, sim state, and service state canonical inside the repo/runtime.

## External References

- Discord application commands: https://discord.com/developers/docs/interactions/application-commands
- Discord interactions receive/respond: https://discord.com/developers/docs/interactions/receiving-and-responding
- Discord gateway intents: https://discord.com/developers/docs/events/gateway#gateway-intents
- Discord webhooks: https://discord.com/developers/docs/resources/webhook
- OpenTelemetry overview: https://opentelemetry.io/docs/what-is-opentelemetry/
- GitHub Projects overview: https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects
