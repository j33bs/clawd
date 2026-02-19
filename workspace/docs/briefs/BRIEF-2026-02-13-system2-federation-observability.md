# Brief: System-2 Federation + Observability Integration Contract

## 1) Title
System-2 Federation and Observability: Contract-First Integration Plan

Rationale: A brief should name the workstream unambiguously so reviewers can quickly align on intent and boundaries.

## 2) Context & Objective
System-2 needs a controlled way to federate requests/events across nodes and emit a stable observability stream for audits, debugging, and governance. This brief defines the canonical contracts and an incremental plan to reintroduce federation/observability prototype artifacts via small, reviewable PRs, without changing System-1 behavior by default.

Rationale: A brief should state why the work exists and how it fits the current architecture to prevent scope drift.

## 3) Scope
Included:
- Federation contract surface: envelope format, signing/verification interface (stub allowed initially), transport-agnostic send/receive adapter, and failure semantics (retry/backoff/circuit-breaker).
- Observability contract surface: event emission API, event schema/versioning, redaction requirements, and an append-only event-log sink interface.
- Deterministic contract tests + fixtures proving: gating, redaction, schema stability, and fail-closed behavior where required.

Not included:
- UI panels or operator web dashboards for federation/observability.
- External service deployment (queues, hosted logging, tracing collectors).
- Peer discovery/enrollment automation or trust onboarding flows.
- Any System-1 behavioral changes unless explicitly gated and tested.

Rationale: Explicit inclusions/exclusions are required so reviewers can evaluate each incremental PR against a fixed scope.

## 4) Goals & Success Criteria
Minimal success criteria:
- Default-off gating: federation/observability are inert unless explicitly enabled in System-2.
- Deterministic unit tests cover schema validation, redaction, gating, and error semantics.
- No external network required for core tests.
- No System-1 impact: System-1 behavior remains unchanged when System-2 features are disabled.

Observable outcomes:
- Phase 1 contract tests pass in CI.
- Phase 2 provides a local in-memory harness demonstrating an end-to-end flow (encode -> send -> receive -> emit -> persist -> replay) without network.
- Phase 3 stabilizes an event log format and versioning suitable for audits and replay.

Rationale: Success criteria must be measurable so reviewers can accept/reject changes objectively.

## 5) Deliverables (Incremental)
Phase 1: Contract Test (minimum interface + static invariants; stubbed behavior)
- Add schema/contract tests for envelope and observability events.
- Add redaction tests (no secrets in events/artifacts).
- Add gating tests (disabled => no-op; no file/network side effects).

Phase 2: Core Implementation (federation module + data pipeline)
- Implement envelope encode/decode, signature interface, and a transport adapter behind flags.
- Provide an in-memory transport harness for deterministic integration tests.
- Implement append-only event log sink interface behind flags.

Phase 3: Observability Export (metrics capture, event logging format)
- Finalize event schema versioning and deterministic JSONL output requirements.
- Add replay tooling and cursor semantics only if required; otherwise defer explicitly.

Rationale: Phased deliverables enable small PRs with clear review gates and lower regression risk.

## 6) Interfaces & API Contracts
### 6.1 Federation Contracts (JS interfaces)
All interfaces are System-2 scoped and must be inert when disabled.

Envelope (canonical shape):
```js
/**
 * @typedef {object} FederatedEnvelopeV1
 * @property {'federated_envelope_v1'} type
 * @property {'1'} version
 * @property {string} id                 // stable unique id (uuid or hash)
 * @property {string} ts_utc             // ISO-8601 UTC
 * @property {{ from: string, to: string, topic: string, ttl_ms?: number }} routing
 * @property {object} payload            // JSON-serializable (redacted-at-write)
 * @property {{ alg: string, key_id: string, sig: string }} signature
 * @property {{ applied: boolean, rules_version: string }} redaction
 */
```

Signer/Verifier:
```js
/**
 * @param {Buffer|string} bytes
 * @returns {{ alg: string, key_id: string, sig: string }}
 */
function sign(bytes) {}

/**
 * @param {Buffer|string} bytes
 * @param {{ alg: string, key_id: string, sig: string }} signature
 * @returns {{ ok: boolean, reason?: string }}
 */
function verify(bytes, signature) {}
```

Transport adapter (no network assumptions):
```js
/**
 * @param {FederatedEnvelopeV1} envelope
 * @param {{ timeout_ms?: number, max_retries?: number }} [opts]
 * @returns {Promise<{ ok: boolean, code: string, status?: number }>}
 */
async function sendEnvelope(envelope, opts) {}
```

Federation invariants:
- No secrets in cleartext: payload must be redacted-at-write.
- Deterministic serialization for the same semantic input when signing/hashing is enabled.
- Schema-invalid envelopes are rejected; strictness is governed by System-2 config.

Rationale: Explicit interface contracts allow contract tests to be written first and keep later implementation PRs constrained.

### 6.2 Observability Contracts
Event (canonical shape):
```js
/**
 * @typedef {object} System2EventV1
 * @property {'system2_event_v1'} type
 * @property {'1'} version
 * @property {string} ts_utc                 // ISO-8601 UTC
 * @property {string} event_type             // stable enum-like string
 * @property {'debug'|'info'|'warn'|'error'} level
 * @property {object} payload                // JSON-serializable (redacted-at-write)
 * @property {{ run_id?: string, node_id?: string, subsystem?: string }} context
 */
```

Emitter (async-safe, best-effort):
```js
/**
 * Emit an event without throwing on sink failures by default.
 * Implementations may provide a strict mode that fails closed.
 *
 * @param {string} eventType
 * @param {object} payload
 * @param {object} [context]
 * @returns {Promise<void>}
 */
async function emitSystem2Event(eventType, payload, context) {}
```

Sink (append-only JSONL writer):
```js
/**
 * Append a single event line to an append-only log.
 *
 * Determinism requirement:
 * - The JSON representation must be stable for the same event object.
 * - A single event is written as one line (JSONL).
 *
 * @param {System2EventV1} event
 * @returns {Promise<void>}
 */
async function appendEvent(event) {}
```

Redaction contract:
- Redaction happens at write time (emitter or sink), not at read time.
- The event must carry `redaction.rules_version` (or equivalent) in payload/context if policy requires it.
- At minimum, redact:
  - Authorization headers / bearer tokens
  - API keys in known env var names
  - Any token-like strings that match the project’s redaction rules

Replay/cursor semantics (minimal):
- Optional: a cursor is the byte offset or line index in the JSONL log.
- If replay is introduced, it must be deterministic given a fixed log file and cursor.
- If not required for Phase 1/2, replay tooling is a non-goal and should remain out of runtime paths.

Observability invariants:
- No secrets in written events/artifacts (enforced by tests).
- Stable schema versioning (type + version pinned by contract tests).
- Deterministic JSONL output for fixture-based tests.
- Default no-op when observability is disabled.

Rationale: Observability is only useful if it is stable, redact-safe, and testable; these constraints must be pinned before implementation grows.

## 7) Configuration & Env
Required flags (proposed):
- `system2.federation.enabled` (default: false)
- `system2.observability.enabled` (default: false)
- `system2.federation.strict` (default: true)

Justification for `system2.federation.strict=true` by default:
- Federation introduces cross-node trust boundaries; failing closed on schema/signature violations is safer than best-effort acceptance.

Precedence:
1. Explicit config (highest)
2. Environment variables
3. Defaults (lowest)

System-1 safety statement:
- Federation/observability must not affect System-1 unless explicitly enabled and covered by deterministic tests.

Rationale: Clear gating and precedence rules prevent accidental enablement and keep behavior predictable across environments.

## 8) Test Plan
Phase 1 contract tests:
- Schema validation for `FederatedEnvelopeV1` and `System2EventV1` (fixtures).
- Redaction tests: ensure emitted artifacts contain no secrets/token-like strings.
- Gating tests: disabled flags => no file writes, no network attempts, no side effects.
- Failure semantics tests: strict mode rejects invalid envelopes/events (fail closed where required).

No-network guarantee:
- Core tests must be deterministic and must not require external network access.
- Any “real transport” integration tests must be opt-in and skipped in CI by default.

Deterministic fixtures:
- Snapshot/fixture tests pin stable JSON output and schema versions.
- Replay tests (if implemented) must use fixed JSONL fixtures and stable cursor semantics.

Rationale: The test plan is the enforcement mechanism for the invariants and gating rules in this brief.

## 9) Non-Goals / Exclusions
- Production key management, rotation automation, and peer onboarding workflows.
- Hosted logging/tracing export integrations.
- UI/UX work for federation/observability controls.
- Automatically enabling any cross-node behavior by default.

Rationale: Non-goals constrain the review surface and keep the initial integration incremental and safe.

## 10) Risks & Mitigations
Risks:
- Async/event-driven complexity causing nondeterministic tests.
- Prototype drift during reintroduction from backup artifacts.
- Secret leakage via events/envelopes or logs.
- Accidental enablement affecting System-1 behavior.

Mitigations:
- Contract-first approach: land tests and schema constraints before implementation.
- Strict default-off gating with explicit flags.
- Redaction-at-write contract + regression tests for token-like patterns.
- Small PR phases with narrow, reviewable diffs and fixture-based verification.

Rationale: Explicit risks and mitigations guide reviewer attention and reduce regressions during incremental integration.

