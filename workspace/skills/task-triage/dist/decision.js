"use strict";
function includesSignal(text, signals) {
  const lower = text.toLowerCase();
  return signals.filter((s) => lower.includes(String(s).toLowerCase()));
}
function routeOverride(text, routeOverrides) {
  for (const item of routeOverrides || []) {
    const match = String((item && item.match) || "").toLowerCase();
    if (match && text.toLowerCase().includes(match)) return item;
  }
  return null;
}
function errorEscalation(lastErrorType, errorEscalations) {
  const wanted = String(lastErrorType || "").toUpperCase();
  if (!wanted) return null;
  for (const item of errorEscalations || []) {
    const type = String((item && item.type) || "").toUpperCase();
    if (type && type === wanted) return item;
  }
  return null;
}
function decideTier(input) {
  const task = String(input.task || "");
  const context = String(input.context || "");
  const combined = `${task}\n${context}`;
  const thresholdRemote = Number((input.rules && input.rules.confidence_threshold_remote) ?? 0.7);
  const thresholdHuman = Number((input.rules && input.rules.confidence_threshold_human) ?? 0.5);
  const localTier = input.localSuggestionTier || "LOCAL";
  const localConfidence = Number(input.localConfidence ?? 0);

  const forceHumanSignals = includesSignal(combined, (input.rules && input.rules.signals && input.rules.signals.force_human) || []);
  if (forceHumanSignals.length > 0) {
    return {
      tier: "HUMAN",
      confidence: 1,
      rationale: `Force-human signal matched: ${forceHumanSignals.join(", ")}`,
      notes: { force_human_signals: forceHumanSignals }
    };
  }

  const escalation = errorEscalation(input.lastLocalErrorType || "", (input.rules && input.rules.error_escalations) || []);
  if (escalation) {
    const tier = String(escalation.tier || "REMOTE").toUpperCase();
    const confidence = Number(escalation.confidence ?? 0.9);
    const rationale = String(escalation.rationale || "local mlx unavailable; escalated");
    return {
      tier,
      confidence,
      rationale,
      notes: { error_escalation: true, last_local_error_type: input.lastLocalErrorType || "" }
    };
  }

  const override = routeOverride(combined, (input.rules && input.rules.route_overrides) || []);
  if (override && String(override.tier).toUpperCase() === "HUMAN") {
    return {
      tier: "HUMAN",
      confidence: Math.max(localConfidence, thresholdHuman),
      rationale: String(override.reason || "Route override requires HUMAN mediation."),
      request_for_chatgpt: {
        task,
        context,
        why: String(override.reason || "OpenAI requires human-mediated handoff."),
        expected_output: "Provide concise actionable output with assumptions and risks."
      },
      notes: { route_override: override.match || "" }
    };
  }

  if (localTier === "LOCAL" && localConfidence >= thresholdRemote) {
    return {
      tier: "LOCAL",
      confidence: localConfidence,
      rationale: input.localRationale || "High-confidence local classification.",
      notes: { threshold_remote: thresholdRemote }
    };
  }

  if (localConfidence >= thresholdHuman) {
    return {
      tier: "REMOTE",
      confidence: localConfidence,
      rationale: "Local confidence below LOCAL threshold; escalate to REMOTE orchestrator.",
      notes: { threshold_remote: thresholdRemote, threshold_human: thresholdHuman }
    };
  }

  return {
    tier: "HUMAN",
    confidence: localConfidence,
    rationale: "Confidence too low for REMOTE; escalate to HUMAN.",
    notes: { threshold_human: thresholdHuman }
  };
}
module.exports = { decideTier };
