"use strict";
const rank = { error: 0, warn: 1, info: 2, debug: 3 };
function resolveLevel() {
  const raw = (process.env.OPENCLAW_LOG_LEVEL || "info").toLowerCase();
  if (raw === "error" || raw === "warn" || raw === "info" || raw === "debug") {
    return raw;
  }
  return "info";
}
function log(level, event, data = {}) {
  const threshold = resolveLevel();
  if (rank[level] > rank[threshold]) return;
  const payload = { ts: new Date().toISOString(), level, skill: "mlx-infer", event, ...data };
  process.stdout.write(`${JSON.stringify(payload)}\n`);
}
module.exports = { log };
