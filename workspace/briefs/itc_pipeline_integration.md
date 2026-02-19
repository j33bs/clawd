# ITC Pipeline Integration (Contract-First)

## Context and Objective
SIM_A currently runs pure regime logic and should remain unchanged. SIM_B currently derives ITC sentiment from tagged message JSONL without a stable source contract. This change adds a versioned ITC signal contract and ingestion boundary so SIM_B can consume deterministic, auditable sentiment/regime inputs now, and D_LIVE/E_SIM can reuse the same contract later.

## Scope (This PR)
- Add a versioned ITC signal schema (`v1`) and validation.
- Add pluggable ingestion interface with a deterministic file-drop adapter.
- Persist raw + normalized artifacts with traceable hash linkage.
- Emit minimal JSONL observability events for ingest/select/reject.
- Expose `get_itc_signal(ts_utc, lookback, policy)` as the stable SIM API.
- Wire SIM_B to consume contract-backed signal with bounded tilt and safe fallback.

## Out of Scope (This PR)
- Live Telegram scraping in the new adapter path.
- New external HTTP fetchers.
- Changes to SIM_A decision logic.
- Production routing policy changes for D_LIVE/E_SIM.

## Data Contract (`itc_signal` v1)
- `schema_version` (int, required): fixed `1`
- `source` (string, required): `telegram` | `file` | `manual`
- `ts_utc` (string, required): ISO8601 UTC timestamp
- `window` (string, required): e.g. `1h`, `4h`, `1d`
- `metrics` (object, required):
  - known keys: `risk_on`, `risk_off`, `sentiment`, `regime`, `confidence`
  - extensible for future keys
- `raw_ref` (string, required): artifact path to persisted raw input
- `signature` (string, optional): content hash (`sha256:<hex>`)

Versioning rule: additive fields only for minor evolution; bump `schema_version` on breaking contract changes.

## Ingestion Adapters
Interface methods:
- `fetch_raw()` -> raw payload + metadata
- `parse_normalize(raw)` -> `itc_signal` object
- `validate(signal)` -> strict contract checks

Adapters in this PR:
- `FileDropAdapter`: deterministic read from `workspace/data/itc/inbox/` (or explicit path)
- Telegram export parser can be added behind same interface without changing consumers.

## Storage Layout
- Raw: `workspace/artifacts/itc/raw/YYYY/MM/DD/<source>_<ts>_<hash8>.<ext>`
- Normalized: `workspace/artifacts/itc/normalized/YYYY/MM/DD/itc_signal_<ts>_<hash8>.json`
- Events: `workspace/artifacts/itc/events/itc_events.jsonl`

Determinism:
- Filenames derive from signal timestamp + content hash.
- Identical source payload yields identical signature and stable normalized content.

## Observability Events (JSONL)
- `itc_ingest_started`
- `itc_raw_stored`
- `itc_normalized_valid`
- `itc_signal_selected`
- `itc_signal_rejected`
- `sim_b_tilt_applied`

Minimal event fields:
- `event_type`, `ts_utc`, `run_id`, `payload`

## Failure Semantics
- Missing feed: `reason=missing`, SIM_B reverts to base weights (tilt=0)
- Stale feed: `reason=stale`, SIM_B reverts to base weights
- Invalid feed: `reason=invalid`, SIM_B reverts to base weights
- Parse errors: event logged; ingest call fails fast for that artifact only

## Governance and Promotion Gates
SIM_B may rely on ITC contract only when:
- schema validation pass rate >= 99% on fixture/backfill set
- stale rate below configured threshold over burn-in window
- bounded tilt behavior verified in replay tests

Kill-switch:
- disable ITC influence by policy (`lookback`/selection returns non-`ok` => zero tilt)
- no contract changes required to switch sources or routing budgets (LOAR-aligned)
