import fs from "node:fs";
import path from "node:path";
import { spawn, spawnSync, type ChildProcessWithoutNullStreams } from "node:child_process";

type Input = {
  prompt?: string;
  model?: string;
  max_tokens?: number;
  temperature?: number;
  model_path?: string;
  config?: string;
  dry_run?: boolean;
};

type CliErrorType =
  | "MODEL_NOT_FOUND"
  | "OOM"
  | "CONCURRENCY_LIMIT"
  | "PYTHON_MISSING"
  | "MLX_MISSING"
  | "INVALID_ARGS"
  | "RUNTIME";

function printOk(payload: Record<string, unknown>): never {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
  process.exit(0);
}

function printErr(type: CliErrorType, message: string, details: Record<string, unknown> = {}): never {
  process.stdout.write(`${JSON.stringify({ ok: false, error: { type, message, details } })}\n`);
  process.exit(1);
}

function parseArgs(argv: string[]): Input {
  const out: Input = {};
  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    const val = argv[i + 1];
    if (key === "--dry-run") {
      out.dry_run = true;
      continue;
    }
    if (!val) {
      printErr("INVALID_ARGS", `missing value for ${key}`);
    }
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

async function readStdinJson(): Promise<Partial<Input>> {
  if (process.stdin.isTTY) return {};
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) chunks.push(Buffer.from(chunk));
  const raw = Buffer.concat(chunks).toString("utf8").trim();
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch (err) {
    printErr("INVALID_ARGS", `stdin JSON parse failed: ${String(err)}`);
  }
}

function loadConfig(configArg?: string): Record<string, unknown> {
  const cfgPath = configArg || process.env.OPENCLAW_SKILL_CONFIG;
  if (!cfgPath) return {};
  try {
    return JSON.parse(fs.readFileSync(cfgPath, "utf8"));
  } catch (err) {
    printErr("INVALID_ARGS", `failed to load config: ${String(err)}`, { config: cfgPath });
  }
}

function ensurePython(): void {
  const check = spawnSync("python3", ["--version"], { encoding: "utf8" });
  if (check.error || check.status !== 0) {
    printErr("PYTHON_MISSING", "python3 not available", { stderr: check.stderr || "" });
  }
}

function ensureMlxImport(): void {
  const check = spawnSync("python3", ["-c", "import mlx_lm"], { encoding: "utf8" });
  if (check.error || check.status !== 0) {
    printErr("MLX_MISSING", "mlx_lm import failed", { stderr: check.stderr || "" });
  }
}

function runDir(baseDir: string): string {
  const d = path.join(baseDir, ".run", "mlx-infer");
  fs.mkdirSync(d, { recursive: true });
  return d;
}

function cleanupStale(dir: string): void {
  for (const file of fs.readdirSync(dir)) {
    if (!file.startsWith("pid-")) continue;
    const parts = file.split("-");
    const pid = Number(parts[1]);
    if (!Number.isFinite(pid)) continue;
    try {
      process.kill(pid, 0);
    } catch {
      fs.rmSync(path.join(dir, file), { force: true });
    }
  }
}

function acquireSlot(baseDir: string, limit: number): () => void {
  const dir = runDir(baseDir);
  cleanupStale(dir);
  const slot = `pid-${process.pid}-${Date.now()}`;
  const slotPath = path.join(dir, slot);
  fs.writeFileSync(slotPath, "1", { encoding: "utf8", flag: "wx" });
  const count = fs.readdirSync(dir).filter((f) => f.startsWith("pid-")).length;
  if (count > limit) {
    fs.rmSync(slotPath, { force: true });
    printErr("CONCURRENCY_LIMIT", `mlx-infer concurrency limit exceeded`, { limit });
  }
  return () => {
    fs.rmSync(slotPath, { force: true });
  };
}

function mapPythonError(type: string): CliErrorType {
  if (type === "MODEL_NOT_FOUND") return "MODEL_NOT_FOUND";
  if (type === "OOM") return "OOM";
  if (type === "INVALID_ARGS") return "INVALID_ARGS";
  return "RUNTIME";
}

function buildPythonArgs(input: Required<Pick<Input, "prompt">> & Input): string[] {
  const script = path.join(__dirname, "..", "scripts", "mlx_infer.py");
  const args: string[] = [script, "--prompt", input.prompt];
  if (input.model) args.push("--model", input.model);
  if (input.model_path) args.push("--model_path", input.model_path);
  if (input.max_tokens !== undefined) args.push("--max_tokens", String(input.max_tokens));
  if (input.temperature !== undefined) args.push("--temperature", String(input.temperature));
  if (input.config) args.push("--config", input.config);
  return args;
}

function spawnPython(args: string[], timeoutMs: number): Promise<{ stdout: string; stderr: string; code: number }> {
  return new Promise((resolve) => {
    const proc: ChildProcessWithoutNullStreams = spawn("python3", args, { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => {
      proc.kill("SIGKILL");
      resolve({ stdout, stderr: `${stderr}\nprocess timeout`, code: 124 });
    }, timeoutMs);
    proc.stdout.on("data", (d) => {
      stdout += d.toString();
    });
    proc.stderr.on("data", (d) => {
      stderr += d.toString();
    });
    proc.on("close", (code) => {
      clearTimeout(timer);
      resolve({ stdout, stderr, code: code ?? 1 });
    });
  });
}

async function main(): Promise<void> {
  const flagArgs = parseArgs(process.argv.slice(2));
  const stdinInput = await readStdinJson();
  const merged: Input = { ...stdinInput, ...flagArgs };
  const cfg = loadConfig(merged.config);

  ensurePython();
  ensureMlxImport();

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
  const release = acquireSlot(baseDir, maxConcurrent);
  try {
    const args = buildPythonArgs({ ...merged, model, prompt: merged.prompt });
    const result = await spawnPython(args, 120000);
    let payload: any;
    try {
      payload = JSON.parse(result.stdout.trim());
    } catch (err) {
      printErr("RUNTIME", "python returned malformed JSON", { stderr: result.stderr, stdout: result.stdout, parse_error: String(err) });
    }
    if (!payload || payload.ok !== true) {
      const pType = payload?.error?.type ? String(payload.error.type) : "RUNTIME";
      const mapped = mapPythonError(pType);
      printErr(mapped, String(payload?.error?.message || "python process failed"), {
        stderr: result.stderr,
        details: payload?.error?.details || {},
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

main().catch((err) => {
  printErr("RUNTIME", `unexpected failure: ${String(err)}`);
});
