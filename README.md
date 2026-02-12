# Source — System README

**Source** - built on Open Claw - is a governed, Law Of Accelerating Returns (LOAR)‑aligned, dual‑gateway AI operations platform designed for frugal, reliable local/hybrid inference with explicit policy control, evidence‑gated workflows, and reversible evolution. It treats agents as **infrastructure**, not chatbots.

The platform consists of **System‑1** and **System‑2** as **co‑equal, permanent** subsystems with a shared policy contract and federated RPC. Scale is achieved by changing **policy knobs** (routing, budgets, limits, concurrency), not by rewriting contracts or data formats.

---

## Goals

* **Reliability first.** Deterministic behavior, bounded retries, circuit breakers, and cooldowns.
* **Frugality.** Prefer local inference; escalate only when policy demands.
* **Governance over convenience.** Explicit, inspectable routing and budget policies.
* **Reversibility.** Proposal‑first changes, minimal diffs, promotion gates, and easy rollback.
* **Evidence‑gated outputs.** Every critical workflow emits verifiable artifacts.
* **LOAR alignment.** Future compute increases adjust policies, not architecture.

---

## Architecture (High Level)

* **Gateways**

  * **System‑1 (Tier‑0/Tier‑1):** Primary execution gateway. Frugal, local‑first, stable.
  * **System‑2 (Tier‑1/Tier‑2):** Peer gateway for complementary capacity and roles. Permanent, not experimental.

* **Routing & Policy**

  * Shared, inspectable **Routing Policy Contract** (pure decision function).
  * Inputs: request class, budgets, quotas, provider health, cooldown state, latency targets.
  * Outputs: model/provider choice, concurrency limits, retry/circuit behavior.

* **Inference Backbone**

  * **vLLM** (preferred) or **Ollama** for local inference.
  * Cheap coordinator model for planning/routing.
  * Strong 70B‑class open models (4–5 bit) for execution when policy allows.

* **Tool Plane**

  * **MCP** with strict allowlists and sandboxing.
  * MCPorter for discovery/CLI workflows.

* **Inter‑Gateway Comms**

  * **Federated RPC** (submit / poll / stream / cancel) with signed, auditable envelopes.

* **Memory & Logs**

  * Central memory with offline‑first local caches.
  * Append‑only event logs + cursor‑based sync.
  * Unified observability schema across both systems.

---

## Governance Model

* **Repo‑as‑Canonical.** The Git repo is the source of truth.
* **Proposal‑First.** Changes land as proposals with scope, constraints, and acceptance criteria.
* **Promotion Gates.** Sim → Staging → Live with evidence checks.
* **Minimal Diff.** Avoid broad refactors; keep changes reversible.
* **No Secrets in Repo.** Enforced via scrubbers and CI gates.
* **CBP Filter.** Default to contemporary best practice unless a principled deviation is stated.

---

## Operational Modes

* **Execution Mode (default).** Ship minimal, safe, reversible changes.
* **Exploratory / Adversarial Mode.** Used only when it improves outcomes; still CBP‑governed.

---

## Workflows

* **Daily Ops**

  * Local‑first execution.
  * Evidence artifacts emitted for audits and reviews.
  * Budget/quota aware routing.

* **Audits**

  * System‑1 and System‑2 have dedicated audit commands.
  * CI validates evidence shape, logs, and exit codes.

* **Simulations & Live Gates**

  * Separate tracks for simulation and live runs.
  * Unified economics logging, strict budgets, kill‑switches.
  * Promote / kill / redesign gates are explicit and logged.

---

## LOAR Alignment Rules (Non‑Negotiable)

1. **Scale via policy, not schema.**
2. **Preserve contracts.** New capability changes knobs, not interfaces.
3. **Avoid drift.** Keep gateways symmetric at the policy layer even if roles differ.
4. **Invest to preserve optionality.** Prefer choices that reduce future migration costs.

---

## Safety & Ethics

* No malicious use cases.
* Tooling is sandboxed and allow‑listed.
* Adversarial testing is explicit and segregated.
* Logs and artifacts are auditable.

---

## Repository Layout (Indicative)

* `openclaw.json` — Core configuration and policy knobs.
* `agents/` — Agent definitions and defaults.
* `core/` — Runners, providers, resilience, routing.
* `scripts/` — Diagnostics, audits, scrubbing, helpers.
* `workspace/` — Evidence artifacts, briefs, snapshots.
* `.github/` — CI, audit workflows, gates.

---

## Getting Started

1. **Clone the repo** (repo is canonical).
2. **Configure local inference** (vLLM or Ollama).
3. **Set budgets and routing policy** in `openclaw.json`.
4. **Run audits** for System‑1 and System‑2.
5. **Operate local‑first; escalate by policy only.**

---

## Change Policy (TL;DR)

* Small, reversible, evidence‑backed.
* Proposal → Implement → Regress → Admit.
* If it breaks LOAR alignment, stop and redesign.

---

## Status

OpenClaw is an evolving but **stable** dual‑gateway system. System‑1 and System‑2 are permanent peers. Future work includes scheduled workloads and rentable external compute, integrated without breaking contracts or LOAR alignment.
