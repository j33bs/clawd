export type LogLevel = "error" | "warn" | "info" | "debug";

const rank: Record<LogLevel, number> = {
  error: 0,
  warn: 1,
  info: 2,
  debug: 3,
};

function level(): LogLevel {
  const raw = (process.env.OPENCLAW_LOG_LEVEL || "info").toLowerCase();
  return raw === "error" || raw === "warn" || raw === "info" || raw === "debug" ? raw : "info";
}

export function log(logLevel: LogLevel, event: string, data: Record<string, unknown> = {}): void {
  if (rank[logLevel] > rank[level()]) return;
  const payload = {
    ts: new Date().toISOString(),
    level: logLevel,
    skill: "coreml-embed",
    event,
    ...data,
  };
  process.stderr.write(`${JSON.stringify(payload)}\n`);
}
