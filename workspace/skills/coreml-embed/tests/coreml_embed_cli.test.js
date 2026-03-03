"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { runWithInput } = require("../dist/cli.js");

function baseDeps() {
  return {
    ensureRunnerAvailable: () => {},
    acquireSlot: () => () => {},
    invokeRunner: async () => ({
      stdout: JSON.stringify({ ok: true, model_path: "/tmp/model.mlpackage", dims: 3, embeddings: [[1, 2, 3]], latency_ms: 5 }),
      stderr: "",
      code: 0,
      timed_out: false,
    }),
  };
}

test("enforces max_texts budget", async () => {
  await assert.rejects(
    runWithInput(
      {
        model_path: "/tmp/model.mlpackage",
        texts: ["a", "b"],
        config: `${__dirname}/fixtures/max1.json`,
      },
      baseDeps()
    ),
    (err) => err && err.type === "INVALID_ARGS" && /max_texts/.test(err.message)
  );
});

test("returns embeddings on successful runner output", async () => {
  const out = await runWithInput(
    {
      model_path: "/tmp/model.mlpackage",
      texts: ["hello"],
      config: `${__dirname}/fixtures/default.json`,
    },
    baseDeps()
  );
  assert.equal(out.dims, 3);
  assert.deepEqual(out.embeddings, [[1, 2, 3]]);
});

test("surfaces runner typed error", async () => {
  const deps = baseDeps();
  deps.invokeRunner = async () => ({
    stdout: JSON.stringify({ ok: false, error: { type: "MODEL_NOT_FOUND", message: "missing model", details: { model_path: "x" } } }),
    stderr: "",
    code: 1,
    timed_out: false,
  });
  await assert.rejects(
    runWithInput(
      {
        model_path: "/tmp/missing.mlpackage",
        texts: ["hello"],
        config: `${__dirname}/fixtures/default.json`,
      },
      deps
    ),
    (err) => err && err.type === "MODEL_NOT_FOUND"
  );
});

test("maps runner timeout to RUNNER_TIMEOUT", async () => {
  const deps = baseDeps();
  deps.invokeRunner = async () => ({ stdout: "", stderr: "", code: 124, timed_out: true });
  await assert.rejects(
    runWithInput(
      {
        model_path: "/tmp/model.mlpackage",
        texts: ["hello"],
        config: `${__dirname}/fixtures/default.json`,
      },
      deps
    ),
    (err) => err && err.type === "RUNNER_TIMEOUT"
  );
});

test("health mode passes runner health response through", async () => {
  const deps = baseDeps();
  deps.invokeRunner = async (args) => {
    assert.deepEqual(args.slice(0, 2), ["--health", "--model_path"]);
    return {
      stdout: JSON.stringify({ ok: true, model_path: "/tmp/model.mlpackage", inputs: ["text"], outputs: ["embedding"] }),
      stderr: "",
      code: 0,
      timed_out: false,
    };
  };
  const out = await runWithInput(
    {
      health: true,
      model_path: "/tmp/model.mlpackage",
      config: `${__dirname}/fixtures/default.json`,
    },
    deps
  );
  assert.equal(out.ok, true);
  assert.equal(out.model_path, "/tmp/model.mlpackage");
});
