"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const { selectEvidenceBundle } = require("../dist/evidence_embed.js");

function makeRules(overrides = {}) {
  return {
    confidence_threshold_remote: 0.7,
    confidence_threshold_human: 0.5,
    signals: { force_human: [], prefer_local: [], prefer_remote: [] },
    route_overrides: [],
    error_escalations: [],
    evidence: {
      enabled: true,
      strategy_preference: ["coreml_embed", "keyword_stub"],
      chunk_chars: 30,
      top_k: 2,
      min_score: 0,
      max_context_chars_for_evidence: 20000,
      coreml: {
        enabled: true,
        model_path: "/tmp/fake-model.mlpackage",
        compute_units: "ALL",
        max_texts_per_call: 32,
        timeout_ms: 1000,
        health_check: true,
        circuit_breaker: { failure_window: 10, max_failures: 3, cooloff_ms: 60000 },
      },
      fallback_keyword_stub: { enabled: true },
    },
    ...overrides,
  };
}

test("evidence selector prefers coreml strategy when embeddings succeed", async () => {
  let embedCall = 0;
  const deps = {
    coremlHealth: async () => {},
    coremlEmbed: async (_model, texts) => {
      embedCall += 1;
      if (embedCall === 1) return [[1, 0]]; // query embedding
      return texts.map((t) => (t.includes("alpha") ? [1, 0] : [0, 1]));
    },
  };

  const result = await selectEvidenceBundle(
    "alpha objective",
    "alpha details paragraph\nbeta details paragraph",
    makeRules(),
    deps
  );

  assert.equal(result.bundle.kind, "coreml_embed");
  assert.equal(result.summary.strategy, "coreml_embed");
  assert.equal(result.summary.outcome, "ok");
  assert.ok(result.bundle.selected.length > 0);
});

test("falls back to keyword stub when coreml model_path is not configured", async () => {
  const rules = makeRules({
    evidence: {
      ...makeRules().evidence,
      coreml: { ...makeRules().evidence.coreml, model_path: "" },
    },
  });

  const result = await selectEvidenceBundle(
    "secret handling",
    "this context includes secret rotation guidance",
    rules,
    {}
  );

  assert.equal(result.bundle.kind, "keyword_stub");
  assert.equal(result.summary.outcome, "fallback");
  assert.equal(result.summary.error_type, "EVIDENCE_EMBED_MODEL_NOT_CONFIGURED");
});

test("falls back to keyword stub when coreml embed reports MODEL_NOT_FOUND", async () => {
  const deps = {
    coremlHealth: async () => {},
    coremlEmbed: async () => {
      throw { type: "EVIDENCE_EMBED_UNAVAILABLE", message: "coreml embed unavailable", details: { underlying_type: "MODEL_NOT_FOUND" } };
    },
  };

  const result = await selectEvidenceBundle(
    "architecture review",
    "context chunk one\ncontext chunk two",
    makeRules(),
    deps
  );

  assert.equal(result.bundle.kind, "keyword_stub");
  assert.equal(result.summary.outcome, "fallback");
  assert.equal(result.summary.error_type, "EVIDENCE_EMBED_UNAVAILABLE");
});

test("falls back to keyword stub when coreml embed times out", async () => {
  const deps = {
    coremlHealth: async () => {},
    coremlEmbed: async () => {
      throw { type: "EVIDENCE_EMBED_TIMEOUT", message: "timeout" };
    },
  };

  const result = await selectEvidenceBundle(
    "routing",
    "paragraph one paragraph two paragraph three",
    makeRules(),
    deps
  );

  assert.equal(result.bundle.kind, "keyword_stub");
  assert.equal(result.summary.outcome, "fallback");
  assert.equal(result.summary.error_type, "EVIDENCE_EMBED_TIMEOUT");
});

test("keyword fallback chunking is deterministic", async () => {
  const rules = makeRules({
    evidence: {
      ...makeRules().evidence,
      coreml: { ...makeRules().evidence.coreml, model_path: "" },
      strategy_preference: ["coreml_embed", "keyword_stub"],
    },
  });

  const task = "alpha beta";
  const context = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda";

  const a = await selectEvidenceBundle(task, context, rules, {});
  const b = await selectEvidenceBundle(task, context, rules, {});

  assert.deepEqual(a.bundle.selected, b.bundle.selected);
  assert.equal(a.bundle.stats.truncated, b.bundle.stats.truncated);
});
