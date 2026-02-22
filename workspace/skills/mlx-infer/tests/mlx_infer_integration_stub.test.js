"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");

const { mapPythonError, buildPythonArgs } = require("../dist/cli.js");

test("maps python error types to node-level types", () => {
  assert.equal(mapPythonError("MODEL_NOT_FOUND"), "MODEL_NOT_FOUND");
  assert.equal(mapPythonError("OOM"), "OOM");
  assert.equal(mapPythonError("INVALID_ARGS"), "INVALID_ARGS");
  assert.equal(mapPythonError("WHATEVER"), "RUNTIME");
});

test("buildPythonArgs includes required and optional args", () => {
  const args = buildPythonArgs({
    prompt: "hello",
    model: "qwen",
    max_tokens: 12,
    temperature: 0.2,
    model_path: "./models",
    config: "./cfg.json"
  });
  assert.ok(args[0].endsWith("scripts/mlx_infer.py"));
  assert.deepEqual(args.slice(1), [
    "--prompt", "hello",
    "--model", "qwen",
    "--model_path", "./models",
    "--max_tokens", "12",
    "--temperature", "0.2",
    "--config", "./cfg.json"
  ]);
});
