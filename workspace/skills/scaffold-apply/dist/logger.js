"use strict";
const rank = { error: 0, warn: 1, info: 2, debug: 3 };
function getLevel() {
  const raw = (process.env.OPENCLAW_LOG_LEVEL || "info").toLowerCase();
  return raw === "error" || raw === "warn" || raw === "info" || raw === "debug" ? raw : "info";
}
function log(level, event, data = {}) {
  if (rank[level] > rank[getLevel()]) return;
  process.stdout.write(`${JSON.stringify({ ts: new Date().toISOString(), level, skill: "scaffold-apply", event, ...data })}\n`);
}
module.exports = { log };
