"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { once } = require("node:events");

const CLI_PATH = path.resolve(__dirname, "../dist/cli.js");

function canSpawnNode() {
  const { spawnSync } = require("node:child_process");
  const probe = spawnSync(process.execPath, ["-e", "process.exit(0)"], { encoding: "utf8" });
  return !probe.error;
}

async function runSnippet(snippet) {
  const child = spawn(process.execPath, ["-e", snippet], { stdio: ["ignore", "pipe", "pipe"] });
  let stdout = "";
  let stderr = "";
  child.stdout.on("data", (d) => {
    stdout += d.toString("utf8");
  });
  child.stderr.on("data", (d) => {
    stderr += d.toString("utf8");
  });
  const [code] = await once(child, "close");
  return { code, stdout: stdout.trim(), stderr: stderr.trim() };
}

test("preflight nonzero exit returns MLX_DEVICE_UNAVAILABLE", async (t) => {
  if (!canSpawnNode()) {
    t.skip("subprocess spawn unavailable in this environment");
    return;
  }
  const snippet = `
    const cli = require(${JSON.stringify(CLI_PATH)});
    cli.run([], {
      ensurePython: () => {},
      runMlxPreflight: async () => ({ code: 1, timed_out: false, stdout: "", stderr: "device lookup failed" }),
      ensureMlxImport: () => { throw new Error("ensureMlxImport should not run"); },
      acquireSlot: () => () => {}
    }).catch(() => {});
  `;
  const result = await runSnippet(snippet);
  assert.equal(result.code, 1);
  const payload = JSON.parse(result.stdout);
  assert.equal(payload.error.type, "MLX_DEVICE_UNAVAILABLE");
  assert.equal(payload.error.details.exit_code, 1);
  assert.equal(payload.error.details.timed_out, false);
  assert.match(payload.error.details.stderr_head, /device lookup failed/);
  assert.match(result.stderr, /"stage":"mlx_preflight"/);
  assert.match(result.stderr, /"outcome":"fail"/);
});

test("preflight timeout returns MLX_DEVICE_UNAVAILABLE", async (t) => {
  if (!canSpawnNode()) {
    t.skip("subprocess spawn unavailable in this environment");
    return;
  }
  const snippet = `
    const cli = require(${JSON.stringify(CLI_PATH)});
    cli.run([], {
      ensurePython: () => {},
      runMlxPreflight: async () => ({ code: 124, timed_out: true, stdout: "", stderr: "process timeout" }),
      ensureMlxImport: () => { throw new Error("ensureMlxImport should not run"); },
      acquireSlot: () => () => {}
    }).catch(() => {});
  `;
  const result = await runSnippet(snippet);
  assert.equal(result.code, 1);
  const payload = JSON.parse(result.stdout);
  assert.equal(payload.error.type, "MLX_DEVICE_UNAVAILABLE");
  assert.equal(payload.error.details.exit_code, 124);
  assert.equal(payload.error.details.timed_out, true);
  assert.match(payload.error.details.stderr_head, /process timeout/);
  assert.match(result.stderr, /"stage":"mlx_preflight"/);
  assert.match(result.stderr, /"outcome":"fail"/);
});

test("preflight ok proceeds to generation path", async (t) => {
  if (!canSpawnNode()) {
    t.skip("subprocess spawn unavailable in this environment");
    return;
  }
  const snippet = `
    const cli = require(${JSON.stringify(CLI_PATH)});
    cli.run(["--prompt", "hello", "--model", "demo"], {
      ensurePython: () => {},
      runMlxPreflight: async () => ({ code: 0, timed_out: false, stdout: "Device(gpu, 0)\\n", stderr: "" }),
      ensureMlxImport: () => {},
      acquireSlot: () => () => {},
      spawnPython: async () => ({
        stdout: JSON.stringify({ ok: true, completion: "ok", latency_ms: 5, tokens_used: 2 }),
        stderr: "",
        code: 0
      })
    }).catch((err) => {
      process.stderr.write(String(err));
      process.exit(99);
    });
  `;
  const result = await runSnippet(snippet);
  assert.equal(result.code, 0);
  const payload = JSON.parse(result.stdout);
  assert.equal(payload.completion, "ok");
  assert.equal(payload.latency_ms, 5);
  assert.equal(payload.tokens_used, 2);
  assert.match(result.stderr, /"stage":"mlx_preflight"/);
  assert.match(result.stderr, /"outcome":"ok"/);
});
