"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { validatePlanInput } = require("../dist/plan_schema.js");

test("validation fails when required fields are missing", () => {
  const result = validatePlanInput({});
  assert.equal(result.valid, false);
  assert.match(result.errors.join(" | "), /target_dir/);
  assert.match(result.errors.join(" | "), /plan/);
});

test("validation fails invalid operation", () => {
  const result = validatePlanInput({
    target_dir: ".",
    plan: [{ file: "a.txt", operation: "move", rationale: "x" }],
  });
  assert.equal(result.valid, false);
  assert.match(result.errors.join(" | "), /operation/);
});

test("validation rejects path traversal", () => {
  const result = validatePlanInput({
    target_dir: ".",
    plan: [{ file: "../etc/passwd", operation: "create", content: "x", rationale: "x" }],
  });
  assert.equal(result.valid, false);
  assert.match(result.errors.join(" | "), /must not escape target_dir/);
});
