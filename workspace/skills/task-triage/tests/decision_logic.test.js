"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { decideTier } = require("../dist/decision.js");

const rules = JSON.parse(
  fs.readFileSync(path.join(__dirname, "..", "config", "decision_rules.json"), "utf8")
);

test("high-confidence LOCAL remains LOCAL", () => {
  const result = decideTier({
    task: "summarize changelog",
    context: "",
    localSuggestionTier: "LOCAL",
    localConfidence: 0.91,
    localRationale: "simple",
    rules,
  });
  assert.equal(result.tier, "LOCAL");
});

test("low confidence escalates to REMOTE", () => {
  const result = decideTier({
    task: "architect distributed service",
    context: "",
    localSuggestionTier: "LOCAL",
    localConfidence: 0.62,
    localRationale: "mixed",
    rules,
  });
  assert.equal(result.tier, "REMOTE");
});

test("very low confidence escalates to HUMAN", () => {
  const result = decideTier({
    task: "unclear request",
    context: "",
    localSuggestionTier: "LOCAL",
    localConfidence: 0.22,
    localRationale: "unknown",
    rules,
  });
  assert.equal(result.tier, "HUMAN");
});

test("force_human signal triggers HUMAN", () => {
  const result = decideTier({
    task: "please delete prod data now",
    context: "",
    localSuggestionTier: "LOCAL",
    localConfidence: 0.95,
    localRationale: "high",
    rules,
  });
  assert.equal(result.tier, "HUMAN");
});

test("openai keyword triggers HUMAN plus request_for_chatgpt", () => {
  const result = decideTier({
    task: "use openai to draft a legal argument",
    context: "customer escalation",
    localSuggestionTier: "REMOTE",
    localConfidence: 0.7,
    localRationale: "complex",
    rules,
  });
  assert.equal(result.tier, "HUMAN");
  assert.ok(result.request_for_chatgpt);
  assert.equal(typeof result.request_for_chatgpt.expected_output, "string");
});
