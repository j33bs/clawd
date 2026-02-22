"use strict";
const fs = require("node:fs");
const path = require("node:path");
const { decideTier } = require("./decision");

function die(message) {
  process.stdout.write(`${JSON.stringify({ ok: false, error: { type: "INVALID_ARGS", message } })}\n`);
  process.exit(1);
}

async function readInput() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(Buffer.from(chunk));
  const raw = Buffer.concat(chunks).toString("utf8").trim();
  if (!raw) die("stdin JSON is required");
  try {
    return JSON.parse(raw);
  } catch (err) {
    die(`stdin JSON parse failed: ${String(err)}`);
  }
}

function loadRules() {
  const base = path.join(__dirname, "..");
  const rulesPath = path.join(base, "config", "decision_rules.json");
  return JSON.parse(fs.readFileSync(rulesPath, "utf8"));
}

function appendAudit(event) {
  const base = path.join(__dirname, "..");
  const auditDir = path.join(base, "audit");
  fs.mkdirSync(auditDir, { recursive: true });
  const line = JSON.stringify(event);
  process.stderr.write(`${line}\n`);
  fs.appendFileSync(path.join(auditDir, "triage.jsonl"), `${line}\n`, "utf8");
}

async function run() {
  const input = await readInput();
  if (!input.task || typeof input.task !== "string") die("task is required");

  const rules = loadRules();
  const decision = decideTier({
    task: input.task,
    context: input.context || "",
    lastLocalErrorType: (input.last_local_error && input.last_local_error.type) || "",
    localSuggestionTier: (input.local && input.local.tier_suggestion) || "LOCAL",
    localConfidence: Number((input.local && input.local.confidence) ?? 0),
    localRationale: (input.local && input.local.rationale) || "",
    rules,
  });

  appendAudit({
    ts: new Date().toISOString(),
    skill: "task-triage",
    event: "triage",
    tier: decision.tier,
    confidence: decision.confidence,
    signals: decision.notes || {},
  });

  const output = {
    tier: decision.tier,
    confidence: decision.confidence,
    rationale: decision.rationale,
  };
  if (decision.request_for_chatgpt) output.request_for_chatgpt = decision.request_for_chatgpt;

  process.stdout.write(`${JSON.stringify(output)}\n`);
}

if (require.main === module) {
  run().catch((err) => {
    process.stdout.write(`${JSON.stringify({ ok: false, error: { type: "RUNTIME", message: String(err) } })}\n`);
    process.exit(1);
  });
}

module.exports = { run };
