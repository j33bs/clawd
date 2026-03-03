"use strict";
const rank = { error: 0, warn: 1, info: 2, debug: 3 };
function level() {
  const raw = (process.env.OPENCLAW_LOG_LEVEL || "info").toLowerCase();
  return raw === "error" || raw === "warn" || raw === "info" || raw === "debug" ? raw : "info";
}
function log(logLevel, event, data = {}) {
  if (rank[logLevel] > rank[level()]) return;
  const payload = { ts: new Date().toISOString(), level: logLevel, skill: "task-triage", event, ...data };
  process.stdout.write(`${JSON.stringify(payload)}\n`);
}
module.exports = { log };
