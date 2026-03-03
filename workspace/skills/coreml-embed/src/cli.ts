import fs from "node:fs";
import path from "node:path";
import { spawn, spawnSync, type ChildProcessWithoutNullStreams } from "node:child_process";
import { log } from "./logger";

type ComputeUnits = "ALL" | "CPU_ONLY" | "CPU_AND_GPU" | "CPU_AND_NE";

type InputPayload = {
  model_path?: string;
  texts?: string[];
  max_text_chars?: number;
  compute_units?: ComputeUnits;
  dry_run?: boolean;
  health?: boolean;
  config?: string;
};

type Config = {
  max_concurrent?: number;
  max_texts?: number;
  default_compute_units?: ComputeUnits;
  runner_timeout_ms?: number;
};

type RunnerResult = {
  stdout: string;
  stderr: string;
  code: number;
  timed_out: boolean;
};

type CliErrorType =
  | "RUNNER_MISSING"
  | "RUNNER_BUILD_FAILED"
  | "RUNNER_TIMEOUT"
  | "CONCURRENCY_LIMIT"
  | "INVALID_ARGS"
  | "RUNTIME";

const DEFAULT_PID_TTL_MS = 600000;
const VALID_COMPUTE_UNITS: ComputeUnits[] = ["ALL", "CPU_ONLY", "CPU_AND_GPU", "CPU_AND_NE"];

export class CliFailure extends Error {
  type: string;
  details: Record<string, unknown>;

  constructor(type: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.type = type;
    this.details = details;
  }
}

function fail(type: string, message: string, details: Record<string, unknown> = {}): never {
  throw new CliFailure(type, message, details);
}

function printOk(payload: Record<string, unknown>): never {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
  process.exit(0);
}

function printErr(type: string, message: string, details: Record<string, unknown> = {}): never {
  process.stdout.write(`${JSON.stringify({ ok: false, error: { type, message, details } })}\n`);
  process.exit(1);
}

export function parseArgs(argv: string[]): InputPayload {
  const out: InputPayload = {};
  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    if (key === "--dry-run") {
      out.dry_run = true;
      continue;
    }
    if (key === "--health") {
      out.health = true;
      continue;
    }
    const val = argv[i + 1];
    if (val === undefined) fail("INVALID_ARGS", `missing value for ${key}`);
    if (key === "--model_path") out.model_path = val;
    else if (key === "--max_text_chars") out.max_text_chars = Number(val);
    else if (key === "--compute_units") out.compute_units = String(val).toUpperCase() as ComputeUnits;
    else if (key === "--text") out.texts = [...(out.texts || []), val];
    else if (key === "--config") out.config = val;
    else fail("INVALID_ARGS", `unknown flag: ${key}`);
    i += 1;
  }
  return out;
}

async function readStdinJson(): Promise<Partial<InputPayload>> {
  if (process.stdin.isTTY) return {};
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) chunks.push(Buffer.from(chunk));
  const raw = Buffer.concat(chunks).toString("utf8").trim();
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch (err) {
    fail("INVALID_ARGS", `stdin JSON parse failed: ${String(err)}`);
  }
}

function loadConfig(configArg?: string): Config {
  const explicit = configArg || process.env.OPENCLAW_SKILL_CONFIG;
  const defaultPath = path.join(__dirname, "..", "config", "default.json");
  const cfgPath = explicit || defaultPath;
  try {
    return JSON.parse(fs.readFileSync(cfgPath, "utf8"));
  } catch (err) {
    fail("INVALID_ARGS", `failed to load config: ${String(err)}`, { config: cfgPath });
  }
}

function normalizeComputeUnits(value: unknown, fallback: ComputeUnits): ComputeUnits {
  const key = String(value || fallback).toUpperCase() as ComputeUnits;
  if (!VALID_COMPUTE_UNITS.includes(key)) {
    fail("INVALID_ARGS", "compute_units must be one of ALL|CPU_ONLY|CPU_AND_GPU|CPU_AND_NE", {
      compute_units: String(value),
    });
  }
  return key;
}

function runnerScriptPath(): string {
  return path.join(__dirname, "..", "..", "..", "runners", "coreml_embed_runner", "run.sh");
}

function runnerBinaryPath(): string {
  return path.join(__dirname, "..", "..", "..", "runners", "coreml_embed_runner", ".build", "release", "CoreMLEmbedRunner");
}

function ensureRunnerAvailable(): void {
  const script = runnerScriptPath();
  if (!fs.existsSync(script)) {
    fail("RUNNER_MISSING", "coreml embed runner wrapper script not found", { script });
  }
  const binary = runnerBinaryPath();
  if (!fs.existsSync(binary)) {
    const swiftCheck = spawnSync("swift", ["--version"], { encoding: "utf8" });
    if (swiftCheck.error || swiftCheck.status !== 0) {
      fail("RUNNER_MISSING", "swift toolchain not available to build runner", {
        stderr: swiftCheck.stderr || "",
      });
    }
  }
}

function resolveRunnerTimeoutMs(cfg: Config): number {
  const raw = process.env.OPENCLAW_COREML_EMBED_TIMEOUT_MS || String(cfg.runner_timeout_ms || 30000);
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : 30000;
}

function resolveMaxConcurrent(cfg: Config): number {
  const raw = Number(process.env.OPENCLAW_MAX_CONCURRENT || cfg.max_concurrent || 1);
  if (!Number.isFinite(raw) || raw < 1) fail("INVALID_ARGS", "max_concurrent must be >= 1", { max_concurrent: raw });
  return Math.floor(raw);
}

function resolvePidTtlMs(): number {
  const raw = process.env.OPENCLAW_COREML_EMBED_PID_TTL_MS;
  if (!raw) return DEFAULT_PID_TTL_MS;
  const parsed = Number(raw);
  if (!Number.isFinite(parsed) || parsed <= 0) return DEFAULT_PID_TTL_MS;
  return Math.floor(parsed);
}

function runDir(baseDir: string): string {
  const dir = path.join(baseDir, ".run", "coreml-embed");
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function parsePidFromFilename(file: string): number | null {
  const match = /^pid-(\d+)(?:-.+)?$/.exec(file);
  if (!match) return null;
  const pid = Number(match[1]);
  if (!Number.isInteger(pid) || pid < 1) return null;
  return pid;
}

function isPidAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (err: any) {
    if (err?.code === "ESRCH") return false;
    if (err?.code === "EPERM") return true;
    return true;
  }
}

function cleanupStalePidFiles(dir: string, ttlMs: number): void {
  for (const file of fs.readdirSync(dir)) {
    if (!file.startsWith("pid-")) continue;
    const full = path.join(dir, file);
    let stat: fs.Stats;
    try {
      stat = fs.statSync(full);
    } catch (err: any) {
      if (err?.code === "ENOENT") continue;
      continue;
    }
    const expired = Date.now() - stat.mtimeMs > ttlMs;
    const pid = parsePidFromFilename(file);
    const dead = pid !== null ? !isPidAlive(pid) : false;
    if (!expired && !dead) continue;
    try {
      fs.rmSync(full, { force: true });
    } catch (err: any) {
      if (err?.code === "ENOENT") continue;
    }
  }
}

function acquireSlot(baseDir: string, limit: number): () => void {
  const dir = runDir(baseDir);
  cleanupStalePidFiles(dir, resolvePidTtlMs());
  const slot = `pid-${process.pid}-${Date.now()}`;
  const slotPath = path.join(dir, slot);
  fs.writeFileSync(slotPath, "1", { encoding: "utf8", flag: "wx" });
  const count = fs.readdirSync(dir).filter((f) => f.startsWith("pid-")).length;
  if (count > limit) {
    fs.rmSync(slotPath, { force: true });
    fail("CONCURRENCY_LIMIT", "coreml-embed concurrency limit exceeded", { limit });
  }
  return () => {
    fs.rmSync(slotPath, { force: true });
  };
}

function headText(value: string, max = 400): string {
  const out = String(value || "").trim();
  if (out.length <= max) return out;
  return out.slice(0, max);
}

function parseRunnerJson(stdout: string): any {
  const lines = String(stdout || "")
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (lines.length === 0) return null;
  const last = lines[lines.length - 1];
  try {
    return JSON.parse(last);
  } catch {
    return null;
  }
}

async function invokeRunner(args: string[], inputJson: Record<string, unknown> | null, timeoutMs: number): Promise<RunnerResult> {
  return new Promise((resolve) => {
    const proc: ChildProcessWithoutNullStreams = spawn("bash", [runnerScriptPath(), "--json", ...args], {
      stdio: ["pipe", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      proc.kill("SIGKILL");
    }, timeoutMs);

    proc.stdout.on("data", (d) => {
      stdout += d.toString();
    });
    proc.stderr.on("data", (d) => {
      stderr += d.toString();
    });
    proc.on("close", (code) => {
      clearTimeout(timer);
      resolve({ stdout, stderr, code: timedOut ? 124 : (code ?? 1), timed_out: timedOut });
    });

    if (inputJson) proc.stdin.write(JSON.stringify(inputJson));
    proc.stdin.end();
  });
}

function classifyRunnerFailure(stderr: string): CliErrorType {
  const text = String(stderr || "").toLowerCase();
  if (text.includes("swift") && text.includes("not found")) return "RUNNER_MISSING";
  if (text.includes("swift build") || text.includes("error:")) return "RUNNER_BUILD_FAILED";
  return "RUNTIME";
}

function validateInferenceInput(input: InputPayload, cfg: Config): Required<InputPayload> {
  const modelPath = String(input.model_path || "").trim();
  const texts = Array.isArray(input.texts) ? input.texts.map((v) => String(v)) : [];
  const maxTexts = Number(cfg.max_texts ?? 32);
  const maxTextChars = Number(input.max_text_chars ?? 4000);
  const computeUnits = normalizeComputeUnits(input.compute_units, (cfg.default_compute_units || "ALL") as ComputeUnits);

  if (!modelPath) fail("INVALID_ARGS", "model_path is required");
  if (texts.length < 1) fail("INVALID_ARGS", "texts must contain at least one item");
  if (!Number.isFinite(maxTexts) || maxTexts < 1) fail("INVALID_ARGS", "max_texts must be >= 1", { max_texts: maxTexts });
  if (texts.length > maxTexts) fail("INVALID_ARGS", "texts exceeds max_texts budget", { max_texts: maxTexts, count: texts.length });
  if (!Number.isFinite(maxTextChars) || maxTextChars < 1) {
    fail("INVALID_ARGS", "max_text_chars must be >= 1", { max_text_chars: maxTextChars });
  }
  for (const text of texts) {
    if (text.length > maxTextChars) {
      fail("INVALID_ARGS", "text exceeds max_text_chars budget", { max_text_chars: maxTextChars });
    }
  }

  return {
    model_path: modelPath,
    texts,
    max_text_chars: Math.floor(maxTextChars),
    compute_units: computeUnits,
    dry_run: Boolean(input.dry_run),
    health: false,
    config: input.config,
  };
}

type Deps = {
  ensureRunnerAvailable?: () => void;
  acquireSlot?: (baseDir: string, limit: number) => () => void;
  invokeRunner?: (args: string[], inputJson: Record<string, unknown> | null, timeoutMs: number) => Promise<RunnerResult>;
};

export async function runWithInput(input: InputPayload, deps: Deps = {}): Promise<Record<string, unknown>> {
  const usedEnsure = deps.ensureRunnerAvailable || ensureRunnerAvailable;
  const usedAcquire = deps.acquireSlot || acquireSlot;
  const usedInvoke = deps.invokeRunner || invokeRunner;
  const cfg = loadConfig(input.config);
  const timeoutMs = resolveRunnerTimeoutMs(cfg);

  usedEnsure();

  if (input.health) {
    const modelPath = String(input.model_path || "").trim();
    if (!modelPath) fail("INVALID_ARGS", "model_path is required for health mode");
    const computeUnits = normalizeComputeUnits(input.compute_units, (cfg.default_compute_units || "ALL") as ComputeUnits);
    log("info", "runner_invocation", { stage: "health", model_path: modelPath });
    const healthRes = await usedInvoke(["--health", "--model_path", modelPath, "--compute_units", computeUnits], null, timeoutMs);
    if (healthRes.timed_out) {
      fail("RUNNER_TIMEOUT", "coreml runner health check timed out", { timeout_ms: timeoutMs });
    }
    const healthPayload = parseRunnerJson(healthRes.stdout);
    if (healthRes.code !== 0) {
      if (healthPayload?.ok === false && healthPayload?.error?.type) {
        fail(String(healthPayload.error.type), String(healthPayload.error.message || "runner failed"), healthPayload.error.details || {});
      }
      fail(classifyRunnerFailure(healthRes.stderr), "coreml runner health check failed", {
        exit_code: healthRes.code,
        stderr_head: headText(healthRes.stderr),
      });
    }
    if (!healthPayload || healthPayload.ok !== true) {
      fail("RUNTIME", "coreml runner returned malformed health payload", {
        stdout_head: headText(healthRes.stdout),
      });
    }
    return healthPayload;
  }

  const normalized = validateInferenceInput(input, cfg);
  if (normalized.dry_run) {
    return {
      ok: true,
      dry_run: true,
      validated: true,
      max_text_chars: normalized.max_text_chars,
      text_count: normalized.texts.length,
      compute_units: normalized.compute_units,
    };
  }

  const release = usedAcquire(path.join(__dirname, ".."), resolveMaxConcurrent(cfg));
  try {
    log("info", "runner_invocation", { stage: "inference", text_count: normalized.texts.length });
    const runnerInput = {
      model_path: normalized.model_path,
      texts: normalized.texts,
      max_text_chars: normalized.max_text_chars,
      compute_units: normalized.compute_units,
    };
    const runRes = await usedInvoke([], runnerInput, timeoutMs);
    if (runRes.timed_out) {
      fail("RUNNER_TIMEOUT", "coreml runner timed out", { timeout_ms: timeoutMs });
    }

    const payload = parseRunnerJson(runRes.stdout);
    if (runRes.code !== 0) {
      if (payload?.ok === false && payload?.error?.type) {
        fail(String(payload.error.type), String(payload.error.message || "runner failed"), payload.error.details || {});
      }
      fail(classifyRunnerFailure(runRes.stderr), "coreml runner execution failed", {
        exit_code: runRes.code,
        stderr_head: headText(runRes.stderr),
      });
    }

    if (!payload || payload.ok !== true) {
      fail("RUNTIME", "coreml runner returned malformed payload", { stdout_head: headText(runRes.stdout) });
    }

    return {
      model_path: payload.model_path,
      dims: payload.dims,
      embeddings: payload.embeddings,
      latency_ms: payload.latency_ms,
    };
  } finally {
    release();
  }
}

export async function run(argv: string[] = process.argv.slice(2)): Promise<void> {
  const argInput = parseArgs(argv);
  const stdinInput = await readStdinJson();
  const merged: InputPayload = { ...stdinInput, ...argInput };
  const out = await runWithInput(merged);
  printOk(out);
}

if (require.main === module) {
  run().catch((err: any) => {
    if (err instanceof CliFailure) {
      printErr(err.type, err.message, err.details);
    }
    printErr("RUNTIME", String(err));
  });
}
