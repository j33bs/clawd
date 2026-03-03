export type LogLevel = "error" | "warn" | "info" | "debug";

const rank: Record<LogLevel, number> = {
  error: 0,
  warn: 1,
  info: 2,
  debug: 3,
};

function resolveLevel(): LogLevel {
  const raw = (process.env.OPENCLAW_LOG_LEVEL || "info").toLowerCase();
  if (raw === "error" || raw === "warn" || raw === "info" || raw === "debug") {
    return raw;
  }
  return "info";
}

export function log(level: LogLevel, event: string, data: Record<string, unknown> = {}): void {
  const threshold = resolveLevel();
  if (rank[level] > rank[threshold]) {
    return;
  }
  const payload = {
    ts: new Date().toISOString(),
    level,
    skill: "mlx-infer",
    event,
    ...data,
  };
  process.stdout.write(`${JSON.stringify(payload)}\n`);
}
