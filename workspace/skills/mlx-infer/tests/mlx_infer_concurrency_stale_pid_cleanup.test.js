"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { once } = require("node:events");

const { acquireSlot } = require("../dist/cli.js");

function makeBaseDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "mlx-infer-concurrency-"));
}

function getRunDir(baseDir) {
  return path.join(baseDir, ".run", "mlx-infer");
}

test("removes stale pid files for dead processes before counting", async (t) => {
  const baseDir = makeBaseDir();
  t.after(() => fs.rmSync(baseDir, { recursive: true, force: true }));
  const dir = getRunDir(baseDir);
  fs.mkdirSync(dir, { recursive: true });

  const dead = spawn(process.execPath, ["-e", "process.exit(0)"], { stdio: "ignore" });
  await once(dead, "exit");
  const staleFile = path.join(dir, `pid-${dead.pid}-${Date.now()}`);
  fs.writeFileSync(staleFile, "1", "utf8");

  const release = acquireSlot(baseDir, 1);
  release();

  assert.equal(fs.existsSync(staleFile), false);
});

test("removes pid file when ttl is exceeded", (t) => {
  const baseDir = makeBaseDir();
  const prevTtl = process.env.OPENCLAW_MLX_INFER_PID_TTL_MS;
  process.env.OPENCLAW_MLX_INFER_PID_TTL_MS = "1";
  t.after(() => {
    if (prevTtl === undefined) delete process.env.OPENCLAW_MLX_INFER_PID_TTL_MS;
    else process.env.OPENCLAW_MLX_INFER_PID_TTL_MS = prevTtl;
    fs.rmSync(baseDir, { recursive: true, force: true });
  });

  const dir = getRunDir(baseDir);
  fs.mkdirSync(dir, { recursive: true });
  const expiredFile = path.join(dir, `pid-${process.pid}-${Date.now()}`);
  fs.writeFileSync(expiredFile, "1", "utf8");
  const oldSec = (Date.now() - 60_000) / 1000;
  fs.utimesSync(expiredFile, oldSec, oldSec);

  const release = acquireSlot(baseDir, 1);
  release();

  assert.equal(fs.existsSync(expiredFile), false);
});

test("live pid file contributes to concurrency limit", async (t) => {
  const baseDir = makeBaseDir();
  t.after(() => fs.rmSync(baseDir, { recursive: true, force: true }));
  const dir = getRunDir(baseDir);
  fs.mkdirSync(dir, { recursive: true });

  const live = spawn(process.execPath, ["-e", "setInterval(() => {}, 1000)"], { stdio: "ignore" });
  t.after(() => {
    if (!live.killed) live.kill("SIGKILL");
  });

  const liveFile = path.join(dir, `pid-${live.pid}-${Date.now()}`);
  fs.writeFileSync(liveFile, "1", "utf8");

  const probeCode = `
    const { acquireSlot } = require(${JSON.stringify(path.resolve(__dirname, "../dist/cli.js"))});
    acquireSlot(${JSON.stringify(baseDir)}, 1);
    process.stdout.write("ok\\n");
  `;
  const probe = spawn(process.execPath, ["-e", probeCode], { stdio: ["ignore", "pipe", "pipe"] });
  let stdout = "";
  probe.stdout.on("data", (chunk) => {
    stdout += chunk.toString("utf8");
  });

  const [code] = await once(probe, "close");
  assert.equal(code, 1);
  assert.match(stdout, /CONCURRENCY_LIMIT/);
});
