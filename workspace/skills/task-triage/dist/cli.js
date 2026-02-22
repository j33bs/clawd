"use strict";
const fs = require("node:fs");
const path = require("node:path");
const { decideTier } = require("./decision");
const { evaluatePrefilter, decideFromSentinel } = require("./prefilter");
const { buildExcerpt, buildEvidenceBundle } = require("./excerpt");

function die(message) {
  process.stdout.write(`${JSON.stringify({ ok: false, error: { type: "INVALID_ARGS", message } })}\n`);
  process.exit(1);
}

function levelWeight(level) {
  if (level === "debug") return 3;
  if (level === "info") return 2;
  if (level === "warn") return 1;
  return 0;
}

function shouldLog(level) {
  const configured = String(process.env.OPENCLAW_LOG_LEVEL || "info").toLowerCase();
  return levelWeight(level) <= levelWeight(configured);
}

function log(level, event, data) {
  if (!shouldLog(level)) return;
  process.stderr.write(`${JSON.stringify({ ts: new Date().toISOString(), level, skill: "task-triage", event, ...data })}\n`);
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

function findErrorEscalation(type, rules) {
  const target = String(type || "").toUpperCase();
  if (!target) return null;
  for (const item of (rules && rules.error_escalations) || []) {
    if (String((item && item.type) || "").toUpperCase() !== target) continue;
    return {
      tier: String((item && item.tier) || "REMOTE").toUpperCase(),
      confidence: Number((item && item.confidence) ?? 0.9),
      rationale: String((item && item.rationale) || "local error escalated")
    };
  }
  return null;
}

async function run() {
  const input = await readInput();
  if (!input.task || typeof input.task !== "string") die("task is required");

  const rules = loadRules();
  const task = input.task;
  const context = input.context || "";
  const source = input.source || "";
  const prefilter = evaluatePrefilter({ task, context, source, rules });
  log("info", "prefilter", {
    stage: "prefilter",
    decision: prefilter.decision,
    tier: prefilter.tier || null,
    confidence: prefilter.confidence ?? null,
    rationale: prefilter.rationale,
    stats: prefilter.stats,
    flags: prefilter.flags
  });

  const excerptCaps = buildExcerpt(task, context, rules, input.sentinel && input.sentinel.max_excerpt_chars);
  const taskExcerpt = (input.excerpt && input.excerpt.task_excerpt) || excerptCaps.task_excerpt;
  const contextExcerpt = (input.excerpt && input.excerpt.context_excerpt) || excerptCaps.context_excerpt;
  const evidenceBundle = buildEvidenceBundle(taskExcerpt, contextExcerpt, rules);
  const allFlags = [...prefilter.flags, ...excerptCaps.flags];

  if (prefilter.decision === "DROP") {
    const output = {
      action: "DROP",
      confidence: 1,
      rationale: prefilter.rationale,
      flags: allFlags
    };
    appendAudit({
      ts: new Date().toISOString(),
      skill: "task-triage",
      event: "triage",
      action: "DROP",
      confidence: 1,
      signals: { flags: allFlags }
    });
    process.stdout.write(`${JSON.stringify(output)}\n`);
    return;
  }

  if (prefilter.decision === "ESCALATE") {
    const output = {
      action: "PROCESS",
      tier: prefilter.tier || "REMOTE",
      confidence: Number(prefilter.confidence ?? 0.85),
      rationale: prefilter.rationale,
      flags: allFlags
    };
    if (evidenceBundle) output.evidence_bundle = evidenceBundle;
    appendAudit({
      ts: new Date().toISOString(),
      skill: "task-triage",
      event: "triage",
      action: "PROCESS",
      tier: output.tier,
      confidence: output.confidence,
      signals: { flags: allFlags }
    });
    process.stdout.write(`${JSON.stringify(output)}\n`);
    return;
  }

  const pipelineEnabled = (rules && rules.prefilter && rules.prefilter.enabled) !== false;
  let tier = "REMOTE";
  let confidence = 0.7;
  let rationale = "low confidence; escalated";
  let request_for_chatgpt;

  const errorEscalation = findErrorEscalation(input.last_local_error && input.last_local_error.type || "", rules);
  if (errorEscalation) {
    tier = errorEscalation.tier;
    confidence = errorEscalation.confidence;
    rationale = errorEscalation.rationale;
    allFlags.push("ERROR_ESCALATION");
  } else if (pipelineEnabled) {
    const minConfidence = Number((rules && rules.sentinel && rules.sentinel.min_confidence) ?? 0.7);
    const sentinelDecision = decideFromSentinel(input.local_sentinel_result, minConfidence);
    tier = sentinelDecision.tier;
    confidence = sentinelDecision.confidence;
    rationale = sentinelDecision.rationale;
    allFlags.push(...sentinelDecision.flags);
  } else {
    const decision = decideTier({
      task,
      context,
      lastLocalErrorType: input.last_local_error && input.last_local_error.type || "",
      localSuggestionTier: input.local && input.local.tier_suggestion || "LOCAL",
      localConfidence: Number(input.local && input.local.confidence ?? 0),
      localRationale: input.local && input.local.rationale || "",
      rules,
    });
    tier = decision.tier;
    confidence = decision.confidence;
    rationale = decision.rationale;
    request_for_chatgpt = decision.request_for_chatgpt;
  }

  const output = {
    action: "PROCESS",
    tier,
    confidence,
    rationale,
    flags: allFlags
  };
  if (request_for_chatgpt) output.request_for_chatgpt = request_for_chatgpt;
  if (evidenceBundle) output.evidence_bundle = evidenceBundle;

  appendAudit({
    ts: new Date().toISOString(),
    skill: "task-triage",
    event: "triage",
    action: "PROCESS",
    tier,
    confidence,
    signals: { flags: allFlags }
  });

  process.stdout.write(`${JSON.stringify(output)}\n`);
}

if (require.main === module) {
  run().catch((err) => {
    process.stdout.write(`${JSON.stringify({ ok: false, error: { type: "RUNTIME", message: String(err) } })}\n`);
    process.exit(1);
  });
}

module.exports = { run };
