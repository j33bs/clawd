"use strict";
const fs = require("node:fs");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");

function printOk(payload) {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
  process.exit(0);
}

function printErr(type, message, details = {}) {
  process.stdout.write(`${JSON.stringify({ ok: false, error: { type, message, details } })}\n`);
  process.exit(1);
}

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    const val = argv[i + 1];
    if (key === "--dry-run") {
      out.dry_run = true;
      continue;
    }
    if (!val) printErr("INVALID_ARGS", `missing value for ${key}`);
    if (key === "--prompt") out.prompt = val;
    else if (key === "--model") out.model = val;
    else if (key === "--model_path") out.model_path = val;
    else if (key === "--config") out.config = val;
    else if (key === "--max_tokens") out.max_tokens = Number(val);
    else if (key === "--temperature") out.temperature = Number(val);
    else printErr("INVALID_ARGS", `unknown flag: ${key}`);
    i += 1;
  }
  return out;
}

async function readStdinJson() {
  if (process.stdin.isTTY) return {};
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(Buffer.from(chunk));
  const raw = Buffer.concat(chunks).toString("utf8").trim();
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch (err) {
    printErr("INVALID_ARGS", `stdin JSON parse failed: ${String(err)}`);
  }
}

function loadConfig(configArg) {
  const cfgPath = configArg || process.env.OPENCLAW_SKILL_CONFIG;
  if (!cfgPath) return {};
  try {
    return JSON.parse(fs.readFileSync(cfgPath, "utf8"));
  } catch (err) {
    printErr("INVALID_ARGS", `failed to load config: ${String(err)}`, { config: cfgPath });
  }
}

function ensurePython() {
  const check = spawnSync("python3", ["--version"], { encoding: "utf8" });
  if (check.error || check.status !== 0) {
    printErr("PYTHON_MISSING", "python3 not available", { stderr: check.stderr || "" });
  }
}

function ensureMlxImport() {
  const check = spawnSync("python3", ["-c", "import mlx_lm"], { encoding: "utf8" });
  if (check.error || check.status !== 0) {
    printErr("MLX_MISSING", "mlx_lm import failed", { stderr: check.stderr || "" });
  }
}

function runDir(baseDir) {
  const d = path.join(baseDir, ".run", "mlx-infer");
  fs.mkdirSync(d, { recursive: true });
  return d;
}

const DEFAULT_PID_TTL_MS = 600000;

function parsePidFromFilename(file) {
  const match = /^pid-(\d+)(?:-.+)?$/.exec(file);
  if (!match) return null;
  const pid = Number(match[1]);
  if (!Number.isInteger(pid) || pid < 1) return null;
  return pid;
}

function isPidAlive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (err) {
    if (err && err.code === "ESRCH") return false;
    if (err && err.code === "EPERM") return true;
    return true;
  }
}

function isExpiredByTtl(mtimeMs, ttlMs) {
  return Date.now() - mtimeMs > ttlMs;
}

function resolvePidTtlMs() {
  const raw = process.env.OPENCLAW_MLX_INFER_PID_TTL_MS;
  if (!raw) return DEFAULT_PID_TTL_MS;
  const parsed = Number(raw);
  if (!Number.isFinite(parsed) || parsed <= 0) return DEFAULT_PID_TTL_MS;
  return Math.floor(parsed);
}

function cleanupStale(dir, ttlMs) {
  for (const file of fs.readdirSync(dir)) {
    if (!file.startsWith("pid-")) continue;
    const fullPath = path.join(dir, file);
    let stat;
    try {
      stat = fs.statSync(fullPath);
    } catch (err) {
      if (err && err.code === "ENOENT") continue;
      continue;
    }
    let shouldDelete = isExpiredByTtl(stat.mtimeMs, ttlMs);
    if (!shouldDelete) {
      const pid = parsePidFromFilename(file);
      if (pid !== null && !isPidAlive(pid)) {
        shouldDelete = true;
      }
    }
    if (!shouldDelete) continue;
    try {
      fs.rmSync(fullPath, { force: true });
    } catch (err) {
      if (err && err.code === "ENOENT") continue;
    }
  }
}

function acquireSlot(baseDir, limit) {
  const dir = runDir(baseDir);
  cleanupStale(dir, resolvePidTtlMs());
  const slot = `pid-${process.pid}-${Date.now()}`;
  const slotPath = path.join(dir, slot);
  fs.writeFileSync(slotPath, "1", { encoding: "utf8", flag: "wx" });
  const count = fs.readdirSync(dir).filter((f) => f.startsWith("pid-")).length;
  if (count > limit) {
    fs.rmSync(slotPath, { force: true });
    printErr("CONCURRENCY_LIMIT", "mlx-infer concurrency limit exceeded", { limit });
  }
  return () => {
    fs.rmSync(slotPath, { force: true });
  };
}

function mapPythonError(type) {
  if (type === "MODEL_NOT_FOUND") return "MODEL_NOT_FOUND";
  if (type === "OOM") return "OOM";
  if (type === "INVALID_ARGS") return "INVALID_ARGS";
  return "RUNTIME";
}

function buildPythonArgs(input) {
  const script = path.join(__dirname, "..", "scripts", "mlx_infer.py");
  const args = [script, "--prompt", input.prompt];
  if (input.model) args.push("--model", input.model);
  if (input.model_path) args.push("--model_path", input.model_path);
  if (input.max_tokens !== undefined) args.push("--max_tokens", String(input.max_tokens));
  if (input.temperature !== undefined) args.push("--temperature", String(input.temperature));
  if (input.config) args.push("--config", input.config);
  return args;
}

function spawnPython(args, timeoutMs) {
  return new Promise((resolve) => {
    const proc = spawn("python3", args, { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => {
      proc.kill("SIGKILL");
      resolve({ stdout, stderr: `${stderr}\nprocess timeout`, code: 124 });
    }, timeoutMs);
    proc.stdout.on("data", (d) => { stdout += d.toString(); });
    proc.stderr.on("data", (d) => { stderr += d.toString(); });
    proc.on("close", (code) => {
      clearTimeout(timer);
      resolve({ stdout, stderr, code: code ?? 1 });
    });
  });
}

async function run(argv = process.argv.slice(2), deps = {}) {
  const usedSpawn = deps.spawnPython || spawnPython;
  const usedEnsurePy = deps.ensurePython || ensurePython;
  const usedEnsureMlx = deps.ensureMlxImport || ensureMlxImport;
  const usedAcquire = deps.acquireSlot || acquireSlot;

  const flagArgs = parseArgs(argv);
  const stdinInput = await readStdinJson();
  const merged = { ...stdinInput, ...flagArgs };
  const cfg = loadConfig(merged.config);

  usedEnsurePy();
  usedEnsureMlx();

  const maxConcurrent = Number(process.env.OPENCLAW_MAX_CONCURRENT || cfg.max_concurrent || 1);
  if (!Number.isFinite(maxConcurrent) || maxConcurrent < 1) {
    printErr("INVALID_ARGS", "max_concurrent must be >= 1", { max_concurrent: maxConcurrent });
  }

  if (merged.dry_run) {
    printOk({ ok: true, dry_run: true, checked: ["python3", "mlx_lm", "args"] });
  }

  if (!merged.prompt || typeof merged.prompt !== "string" || merged.prompt.trim().length < 1) {
    printErr("INVALID_ARGS", "prompt is required");
  }
  if (merged.max_tokens !== undefined && (!Number.isInteger(merged.max_tokens) || merged.max_tokens < 1)) {
    printErr("INVALID_ARGS", "max_tokens must be an integer >= 1");
  }
  if (merged.temperature !== undefined && (Number.isNaN(merged.temperature) || merged.temperature < 0 || merged.temperature > 2)) {
    printErr("INVALID_ARGS", "temperature must be between 0 and 2");
  }

  const model = merged.model || (typeof cfg.default_model === "string" ? cfg.default_model : undefined);
  if (!model) {
    printErr("INVALID_ARGS", "model missing (use --model or config.default_model)");
  }

  const baseDir = path.join(__dirname, "..");
  const release = usedAcquire(baseDir, maxConcurrent);
  try {
    const args = buildPythonArgs({ ...merged, model, prompt: merged.prompt });
    const result = await usedSpawn(args, 120000);
    let payload;
    try {
      payload = JSON.parse((result.stdout || "").trim());
    } catch (err) {
      printErr("RUNTIME", "python returned malformed JSON", { stderr: result.stderr, stdout: result.stdout, parse_error: String(err) });
    }
    if (!payload || payload.ok !== true) {
      const pType = payload && payload.error && payload.error.type ? String(payload.error.type) : "RUNTIME";
      const mapped = mapPythonError(pType);
      printErr(mapped, String((payload && payload.error && payload.error.message) || "python process failed"), {
        stderr: result.stderr,
        details: (payload && payload.error && payload.error.details) || {},
      });
    }
    printOk({
      completion: String(payload.completion || ""),
      latency_ms: Number(payload.latency_ms || 0),
      tokens_used: Number(payload.tokens_used || 0),
    });
  } finally {
    release();
  }
}

if (require.main === module) {
  run().catch((err) => {
    printErr("RUNTIME", `unexpected failure: ${String(err)}`);
  });
}

module.exports = {
  run,
  parseArgs,
  buildPythonArgs,
  mapPythonError,
  parsePidFromFilename,
  isPidAlive,
  isExpiredByTtl,
  resolvePidTtlMs,
  cleanupStale,
  acquireSlot
};
