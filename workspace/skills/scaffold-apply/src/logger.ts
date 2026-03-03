export type LogLevel = "error" | "warn" | "info" | "debug";

const rank: Record<LogLevel, number> = { error: 0, warn: 1, info: 2, debug: 3 };

function getLevel(): LogLevel {
  const raw = (process.env.OPENCLAW_LOG_LEVEL || "info").toLowerCase();
  return raw === "error" || raw === "warn" || raw === "info" || raw === "debug" ? raw : "info";
}

export function log(level: LogLevel, event: string, data: Record<string, unknown> = {}): void {
  if (rank[level] > rank[getLevel()]) return;
  process.stdout.write(`${JSON.stringify({ ts: new Date().toISOString(), level, skill: "scaffold-apply", event, ...data })}\n`);
}
