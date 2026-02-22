import path from "node:path";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";

export type EvidenceSelected = { id: string; start: number; end: number; score: number };
export type StrategyAttempt = { strategy: string; ok: boolean; latency_ms: number; error_type?: string };
export type EvidenceBundle = {
  kind: "coreml_embed" | "keyword_stub";
  top_k: number;
  selected: EvidenceSelected[];
  notes: string;
  stats: {
    chunks_total: number;
    chunks_used: number;
    truncated: boolean;
    latency_ms: number;
    strategy_attempts: StrategyAttempt[];
  };
};

export type EvidenceSelectorResult = {
  bundle: EvidenceBundle | null;
  summary: {
    strategy: string;
    outcome: "ok" | "fallback" | "disabled";
    attempts: StrategyAttempt[];
    error_type?: string;
  };
};

type Chunk = { id: string; start: number; end: number; text: string };

type EvidenceDeps = {
  coremlHealth?: (modelPath: string, computeUnits: string, timeoutMs: number) => Promise<void>;
  coremlEmbed?: (modelPath: string, texts: string[], computeUnits: string, timeoutMs: number) => Promise<number[][]>;
  nowMs?: () => number;
};

type ProcessResult = { stdout: string; stderr: string; code: number; timedOut: boolean };

type TypedError = { type: string; message: string; details?: Record<string, unknown> };

function makeError(type: string, message: string, details: Record<string, unknown> = {}): TypedError {
  return { type, message, details };
}

function now(deps?: EvidenceDeps): number {
  return deps?.nowMs ? deps.nowMs() : Date.now();
}

function head(value: string, max = 400): string {
  const text = String(value || "").trim();
  return text.length <= max ? text : text.slice(0, max);
}

function tokenize(text: string): string[] {
  const words = String(text || "")
    .toLowerCase()
    .split(/[^a-z0-9_]+/)
    .filter((w) => w.length >= 2);
  return Array.from(new Set(words));
}

function cosine(a: number[], b: number[]): number {
  const n = Math.min(a.length, b.length);
  if (n === 0) return 0;
  let dot = 0;
  let aa = 0;
  let bb = 0;
  for (let i = 0; i < n; i += 1) {
    const av = Number(a[i] || 0);
    const bv = Number(b[i] || 0);
    dot += av * bv;
    aa += av * av;
    bb += bv * bv;
  }
  if (aa <= 0 || bb <= 0) return 0;
  return dot / (Math.sqrt(aa) * Math.sqrt(bb));
}

function lastJsonLine(stdout: string): any {
  const lines = String(stdout || "")
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (lines.length === 0) return null;
  try {
    return JSON.parse(lines[lines.length - 1]);
  } catch {
    return null;
  }
}

function runProcess(cmd: string, args: string[], stdinJson: Record<string, unknown> | null, timeoutMs: number): Promise<ProcessResult> {
  return new Promise((resolve) => {
    const proc: ChildProcessWithoutNullStreams = spawn(cmd, args, { stdio: ["pipe", "pipe", "pipe"] });
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
      resolve({ stdout, stderr, code: timedOut ? 124 : (code ?? 1), timedOut });
    });
    if (stdinJson) proc.stdin.write(JSON.stringify(stdinJson));
    proc.stdin.end();
  });
}

function coremlCliPath(): string {
  return path.join(__dirname, "..", "..", "coreml-embed", "dist", "cli.js");
}

function coremlRunnerPath(): string {
  return path.join(__dirname, "..", "..", "..", "runners", "coreml_embed_runner", "run.sh");
}

async function defaultCoremlHealth(modelPath: string, computeUnits: string, timeoutMs: number): Promise<void> {
  const result = await runProcess("bash", [coremlRunnerPath(), "--health", "--model_path", modelPath, "--compute_units", computeUnits], null, timeoutMs);
  if (result.timedOut) {
    throw makeError("EVIDENCE_EMBED_TIMEOUT", "coreml health check timed out", { timeout_ms: timeoutMs });
  }
  const parsed = lastJsonLine(result.stdout);
  if (result.code !== 0) {
    const underlying = parsed?.error?.type ? String(parsed.error.type) : "HEALTH_FAILED";
    throw makeError("EVIDENCE_EMBED_UNAVAILABLE", "coreml health check failed", {
      underlying_type: underlying,
      stderr_head: head(result.stderr),
      stdout_head: head(result.stdout),
    });
  }
  if (!parsed || parsed.ok !== true) {
    throw makeError("EVIDENCE_EMBED_UNAVAILABLE", "coreml health returned malformed payload", {
      stdout_head: head(result.stdout),
    });
  }
}

async function defaultCoremlEmbed(modelPath: string, texts: string[], computeUnits: string, timeoutMs: number): Promise<number[][]> {
  const input = { model_path: modelPath, texts, compute_units: computeUnits };
  const result = await runProcess("node", [coremlCliPath()], input, timeoutMs);
  if (result.timedOut) {
    throw makeError("EVIDENCE_EMBED_TIMEOUT", "coreml embed invocation timed out", { timeout_ms: timeoutMs });
  }
  const parsed = lastJsonLine(result.stdout);
  if (result.code !== 0) {
    if (parsed?.error?.type) {
      throw makeError("EVIDENCE_EMBED_UNAVAILABLE", "coreml embed unavailable", {
        underlying_type: String(parsed.error.type),
        underlying_message: String(parsed.error.message || ""),
      });
    }
    throw makeError("EVIDENCE_EMBED_UNAVAILABLE", "coreml embed invocation failed", {
      stderr_head: head(result.stderr),
      stdout_head: head(result.stdout),
    });
  }
  if (!parsed || !Array.isArray(parsed.embeddings)) {
    throw makeError("EVIDENCE_EMBED_UNAVAILABLE", "coreml embed returned malformed payload", {
      stdout_head: head(result.stdout),
    });
  }
  return parsed.embeddings as number[][];
}

function normalizeEvidenceConfig(rules: any): any {
  const cfg = rules?.evidence || {};
  return {
    enabled: cfg.enabled !== false,
    strategy_preference: Array.isArray(cfg.strategy_preference) && cfg.strategy_preference.length > 0
      ? cfg.strategy_preference
      : ["coreml_embed", "keyword_stub"],
    chunk_chars: Number(cfg.chunk_chars ?? 800),
    top_k: Number(cfg.top_k ?? 5),
    min_score: Number(cfg.min_score ?? 0),
    max_context_chars_for_evidence: Number(cfg.max_context_chars_for_evidence ?? 20000),
    coreml: {
      enabled: cfg?.coreml?.enabled !== false,
      model_path: String(cfg?.coreml?.model_path || ""),
      compute_units: String(cfg?.coreml?.compute_units || "ALL"),
      max_texts_per_call: Number(cfg?.coreml?.max_texts_per_call ?? 32),
      timeout_ms: Number(cfg?.coreml?.timeout_ms ?? 30000),
      health_check: cfg?.coreml?.health_check !== false,
      circuit_breaker: {
        failure_window: Number(cfg?.coreml?.circuit_breaker?.failure_window ?? 10),
        max_failures: Number(cfg?.coreml?.circuit_breaker?.max_failures ?? 3),
        cooloff_ms: Number(cfg?.coreml?.circuit_breaker?.cooloff_ms ?? 60000),
      },
    },
    fallback_keyword_stub: {
      enabled: cfg?.fallback_keyword_stub?.enabled !== false,
    },
  };
}

function chunkContext(context: string, chunkChars: number, maxContextChars: number): { chunks: Chunk[]; truncated: boolean } {
  const safeChunk = Number.isFinite(chunkChars) && chunkChars > 0 ? Math.floor(chunkChars) : 800;
  const safeMax = Number.isFinite(maxContextChars) && maxContextChars > 0 ? Math.floor(maxContextChars) : 20000;
  const source = String(context || "");
  const truncated = source.length > safeMax;
  const text = truncated ? source.slice(0, safeMax) : source;
  const chunks: Chunk[] = [];
  for (let start = 0; start < text.length; start += safeChunk) {
    const end = Math.min(start + safeChunk, text.length);
    const id = `chunk-${String(chunks.length).padStart(4, "0")}`;
    chunks.push({ id, start, end, text: text.slice(start, end) });
  }
  return { chunks, truncated };
}

function selectKeyword(task: string, chunks: Chunk[], cfg: any, truncated: boolean, attempts: StrategyAttempt[], latencyMs: number): EvidenceBundle {
  const taskTokens = tokenize(task);
  const minScore = Number(cfg.min_score ?? 0);
  const topK = Math.max(1, Math.floor(Number(cfg.top_k ?? 5)));

  const scored = chunks
    .map((chunk) => {
      const chunkTokens = new Set(tokenize(chunk.text));
      let overlap = 0;
      for (const token of taskTokens) {
        if (chunkTokens.has(token)) overlap += 1;
      }
      return { id: chunk.id, start: chunk.start, end: chunk.end, score: overlap };
    })
    .filter((item) => item.score >= minScore)
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      return a.start - b.start;
    })
    .slice(0, topK);

  return {
    kind: "keyword_stub",
    top_k: topK,
    selected: scored,
    notes: "keyword overlap fallback selector",
    stats: {
      chunks_total: chunks.length,
      chunks_used: chunks.length,
      truncated,
      latency_ms: latencyMs,
      strategy_attempts: attempts,
    },
  };
}

async function selectCoreml(task: string, chunks: Chunk[], cfg: any, truncated: boolean, attempts: StrategyAttempt[], deps?: EvidenceDeps): Promise<EvidenceBundle> {
  const modelPath = String(cfg?.coreml?.model_path || "").trim();
  if (!modelPath) {
    throw makeError("EVIDENCE_EMBED_MODEL_NOT_CONFIGURED", "coreml model_path not configured", {});
  }

  const computeUnits = String(cfg?.coreml?.compute_units || "ALL");
  const timeoutMs = Number(cfg?.coreml?.timeout_ms ?? 30000);
  const maxPerCall = Math.max(1, Math.floor(Number(cfg?.coreml?.max_texts_per_call ?? 32)));
  const healthCheck = cfg?.coreml?.health_check !== false;

  const health = deps?.coremlHealth || defaultCoremlHealth;
  const embed = deps?.coremlEmbed || defaultCoremlEmbed;

  const cb = cfg?.coreml?.circuit_breaker || {};
  const maxFailures = Math.max(1, Math.floor(Number(cb.max_failures ?? 3)));
  let failures = 0;

  const tryOrThrow = async <T>(fn: () => Promise<T>): Promise<T> => {
    try {
      return await fn();
    } catch (err: any) {
      failures += 1;
      if (failures >= maxFailures) {
        const type = String(err?.type || "EVIDENCE_EMBED_UNAVAILABLE");
        throw makeError(type, String(err?.message || "coreml evidence failed"), {
          ...(err?.details || {}),
          circuit_open: true,
          failures,
          max_failures: maxFailures,
        });
      }
      throw err;
    }
  };

  if (healthCheck) {
    await tryOrThrow(async () => health(modelPath, computeUnits, timeoutMs));
  }

  const queryVecs = await tryOrThrow(async () => embed(modelPath, [task], computeUnits, timeoutMs));
  const query = queryVecs[0] || [];

  const chunkScores: EvidenceSelected[] = [];
  const topK = Math.max(1, Math.floor(Number(cfg.top_k ?? 5)));
  let chunksUsed = 0;

  for (let i = 0; i < chunks.length; i += maxPerCall) {
    const batch = chunks.slice(i, i + maxPerCall);
    const vectors = await tryOrThrow(async () => embed(modelPath, batch.map((c) => c.text), computeUnits, timeoutMs));
    for (let j = 0; j < batch.length; j += 1) {
      const chunk = batch[j];
      const vec = Array.isArray(vectors[j]) ? vectors[j] : [];
      const score = cosine(query, vec);
      chunkScores.push({ id: chunk.id, start: chunk.start, end: chunk.end, score });
      chunksUsed += 1;
    }
  }

  chunkScores.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    return a.start - b.start;
  });

  return {
    kind: "coreml_embed",
    top_k: topK,
    selected: chunkScores.slice(0, topK),
    notes: "coreml embeddings cosine selector",
    stats: {
      chunks_total: chunks.length,
      chunks_used: chunksUsed,
      truncated,
      latency_ms: 0,
      strategy_attempts: attempts,
    },
  };
}

export async function selectEvidenceBundle(task: string, context: string, rules: any, deps?: EvidenceDeps): Promise<EvidenceSelectorResult> {
  const cfg = normalizeEvidenceConfig(rules);
  const attempts: StrategyAttempt[] = [];

  if (!cfg.enabled || !context) {
    return {
      bundle: null,
      summary: { strategy: "none", outcome: "disabled", attempts },
    };
  }

  const overallStart = now(deps);
  const { chunks, truncated } = chunkContext(context, cfg.chunk_chars, cfg.max_context_chars_for_evidence);
  if (chunks.length === 0) {
    return {
      bundle: {
        kind: "keyword_stub",
        top_k: Math.max(1, Math.floor(Number(cfg.top_k ?? 5))),
        selected: [],
        notes: "no context chunks available",
        stats: { chunks_total: 0, chunks_used: 0, truncated, latency_ms: 0, strategy_attempts: attempts },
      },
      summary: { strategy: "keyword_stub", outcome: "ok", attempts },
    };
  }

  let lastErrorType: string | undefined;

  for (const strategy of cfg.strategy_preference) {
    if (strategy === "coreml_embed" && cfg.coreml.enabled) {
      const start = now(deps);
      try {
        const bundle = await selectCoreml(task, chunks, cfg, truncated, attempts, deps);
        attempts.push({ strategy: "coreml_embed", ok: true, latency_ms: now(deps) - start });
        bundle.stats.strategy_attempts = attempts;
        bundle.stats.latency_ms = now(deps) - overallStart;
        return { bundle, summary: { strategy: "coreml_embed", outcome: "ok", attempts } };
      } catch (err: any) {
        const errorType = String(err?.type || "EVIDENCE_EMBED_UNAVAILABLE");
        lastErrorType = errorType;
        attempts.push({ strategy: "coreml_embed", ok: false, latency_ms: now(deps) - start, error_type: errorType });
        continue;
      }
    }

    if (strategy === "keyword_stub" && cfg.fallback_keyword_stub.enabled) {
      const start = now(deps);
      const bundle = selectKeyword(task, chunks, cfg, truncated, attempts, 0);
      attempts.push({ strategy: "keyword_stub", ok: true, latency_ms: now(deps) - start });
      bundle.stats.strategy_attempts = attempts;
      bundle.stats.latency_ms = now(deps) - overallStart;
      return {
        bundle,
        summary: {
          strategy: "keyword_stub",
          outcome: attempts.some((a) => a.strategy === "coreml_embed" && !a.ok) ? "fallback" : "ok",
          attempts,
          error_type: lastErrorType,
        },
      };
    }
  }

  return {
    bundle: null,
    summary: { strategy: "none", outcome: "disabled", attempts, error_type: lastErrorType },
  };
}
