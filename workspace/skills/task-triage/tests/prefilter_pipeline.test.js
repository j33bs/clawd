"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const { evaluatePrefilter, decideFromSentinel } = require("../dist/prefilter.js");
const { buildExcerpt, buildEvidenceBundle } = require("../dist/excerpt.js");

const rules = JSON.parse(
  fs.readFileSync(path.join(__dirname, "..", "config", "decision_rules.json"), "utf8")
);

test("prefilter escalates REMOTE when context is too large", () => {
  const result = evaluatePrefilter({
    task: "normal task",
    context: "x".repeat(13000),
    source: "",
    rules
  });
  assert.equal(result.decision, "ESCALATE");
  assert.equal(result.tier, "REMOTE");
  assert.equal(result.confidence, 0.85);
});

test("prefilter escalates HUMAN for sensitive regex", () => {
  const result = evaluatePrefilter({
    task: "contains api key information",
    context: "",
    source: "",
    rules
  });
  assert.equal(result.decision, "ESCALATE");
  assert.equal(result.tier, "HUMAN");
  assert.equal(result.confidence, 0.95);
});

test("prefilter drops trivial ping/test input", () => {
  const result = evaluatePrefilter({
    task: "ping",
    context: "",
    source: "",
    rules
  });
  assert.equal(result.decision, "DROP");
});

test("excerpt truncation sets TRUNCATED flag", () => {
  const result = buildExcerpt("a".repeat(5000), "b".repeat(13000), rules, 2000);
  assert.match(result.task_excerpt, /^a+$/);
  assert.match(result.context_excerpt, /^b+$/);
  assert.ok(result.flags.includes("TRUNCATED"));
  assert.ok(result.flags.includes("TASK_TRUNCATED"));
  assert.ok(result.flags.includes("CONTEXT_TRUNCATED"));
});

test("sentinel confidence >= threshold is adopted", () => {
  const result = decideFromSentinel(
    { tier_suggestion: "HUMAN", confidence: 0.9, rationale: "sensitive", labels: ["S"] },
    0.7
  );
  assert.equal(result.tier, "HUMAN");
  assert.equal(result.confidence, 0.9);
  assert.equal(result.rationale, "sensitive");
});

test("sentinel confidence < threshold escalates REMOTE", () => {
  const result = decideFromSentinel(
    { tier_suggestion: "LOCAL", confidence: 0.4, rationale: "weak" },
    0.7
  );
  assert.equal(result.tier, "REMOTE");
  assert.equal(result.rationale, "low confidence; escalated");
});

test("evidence bundle stub produces deterministic top_k selection", () => {
  const customRules = {
    evidence: {
      enabled: true,
      chunk_chars: 50,
      top_k: 2,
      min_score: 1
    }
  };
  const bundle = buildEvidenceBundle("alpha beta", "alpha section\n\nbeta section\n\nunrelated", customRules);
  assert.equal(bundle.kind, "topk_stub");
  assert.equal(bundle.top_k, 2);
  assert.equal(bundle.selected.length, 2);
  assert.ok(bundle.selected[0].start <= bundle.selected[1].start);
});
