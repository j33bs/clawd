# Source UI Agent Integration

Source UI is the read-side operator surface for Source. Other agents should integrate against its structured API rather than scraping the dashboard HTML.

## Primary endpoints

- `GET /api/portfolio`
  Full operator payload for the dashboard.
- `GET /api/tasks`
  Canonical editable tasks plus read-only runtime task overlays.
- `GET /api/runtime-tasks`
  Read-only live session/subagent tasks for cross-node mirroring.
- `GET /api/source-contract`
  Contract summary for agents wiring into Source UI.
- `GET /api/commands/history`
  Recent command history.
- `GET /api/commands/receipts`
  Current command receipts and approval states.

## Task model

- Editable local tasks come from `workspace/source-ui/state/tasks.json`.
- Runtime tasks are observational only and always have `read_only=true`.
- Runtime tasks may include:
  - `node_id`
  - `node_label`
  - `runtime_source`
  - `runtime_source_label`
  - `session_id`
  - `session_key`

Do not PATCH or DELETE runtime tasks. Mutate the owning session or create a separate local follow-up task.

## Cross-node mirroring

Source UI can pull read-only runtime tasks from other nodes using:

- `workspace/source-ui/config/runtime_task_sources.json`

Expected remote shape:

- Node exposes Source UI at `http://<tailscale-ip>:18990`
- Runtime task mirror is available at `http://<tailscale-ip>:18990/api/runtime-tasks`

## Guidance

- Prefer Source UI APIs for operator state.
- Prefer OpenClaw session registries for deeper session internals.
- Do not infer mutability from visual affordances; respect `read_only`.
