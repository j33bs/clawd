'use strict';

/**
 * FreeComputeCloud — Quota-Aware Router Extension
 *
 * Pure function that selects an ordered provider/model preference list
 * based on: task class, budget, latency target, context length,
 * provider health, and quota state.
 *
 * LOAR-aligned: adding more compute later changes only catalog entries
 * and config knobs — not this routing contract.
 */

const { CATALOG } = require('./catalog');

/**
 * Route a request to the best available provider(s).
 *
 * @param {object} params
 * @param {string} params.taskClass       - One of REQUEST_CLASSES
 * @param {number} [params.contextLength] - Estimated input token count
 * @param {string} [params.latencyTarget] - 'low' | 'medium' | 'high'
 * @param {object} [params.budget]        - { maxCostUsd, maxTokens }
 * @param {object} params.providerHealth  - { provider_id → { ok: boolean } }
 * @param {object} params.quotaState      - { provider_id → { allowed: boolean, reason? } }
 * @param {object} params.config          - Output of loadFreeComputeConfig()
 * @returns {{ candidates: Array<{ provider_id, model_id, reason, score }>, explanation: string[] }}
 */
function routeRequest(params) {
  const {
    taskClass,
    contextLength = 0,
    latencyTarget = 'medium',
    budget = {},
    providerHealth = {},
    quotaState = {},
    config
  } = params;

  if (!config || !config.enabled) {
    return {
      candidates: [],
      explanation: ['FreeComputeCloud is disabled (ENABLE_FREECOMPUTE_CLOUD=0)']
    };
  }

  const explanation = [];
  const scored = [];

  for (const provider of CATALOG) {
    const pid = provider.provider_id;

    // ── Feature flag gate ──
    if (pid === 'local_vllm' && !config.vllmEnabled) {
      explanation.push(`${pid}: skipped (ENABLE_LOCAL_VLLM=0)`);
      continue;
    }
    if (!provider.enabled_default && provider.kind === 'external') {
      // Check allowlist
      if (config.providerAllowlist.length > 0 && !config.providerAllowlist.includes(pid)) {
        explanation.push(`${pid}: skipped (not in FREECOMPUTE_PROVIDER_ALLOWLIST)`);
        continue;
      }
    }
    if (config.providerDenylist.includes(pid)) {
      explanation.push(`${pid}: skipped (in FREECOMPUTE_PROVIDER_DENYLIST)`);
      continue;
    }

    // ── Health gate ──
    const health = providerHealth[pid];
    if (health && !health.ok) {
      explanation.push(`${pid}: skipped (unhealthy: ${health.reason || 'unknown'})`);
      continue;
    }

    // ── Quota gate ──
    const quota = quotaState[pid];
    if (quota && !quota.allowed) {
      explanation.push(`${pid}: skipped (quota: ${quota.reason || 'exhausted'})`);
      continue;
    }

    // ── Find matching models for task class ──
    const matchingModels = provider.models.filter((m) =>
      m.task_classes.includes(taskClass)
    );
    if (matchingModels.length === 0) {
      explanation.push(`${pid}: no models for task_class=${taskClass}`);
      continue;
    }

    // ── Context window gate ──
    const viableModels = matchingModels.filter((m) => {
      if (!m.context_window_hint || !contextLength) return true;
      return m.context_window_hint >= contextLength;
    });
    if (viableModels.length === 0) {
      explanation.push(`${pid}: no models with sufficient context window for ${contextLength} tokens`);
      continue;
    }

    // ── Score each viable model ──
    for (const model of viableModels) {
      let score = 0;
      const reasons = [];

      // Prefer local
      if (provider.kind === 'local') {
        score += 100;
        reasons.push('local_preferred');
      }

      // Latency preference
      if (latencyTarget === 'low' && provider.routing_tags.prefers.includes('low_latency')) {
        score += 30;
        reasons.push('low_latency_match');
      }
      if (provider.routing_tags.prefers.includes('free_tier')) {
        score += 20;
        reasons.push('free_tier');
      }

      // Penalize avoids
      if (latencyTarget === 'low' && provider.routing_tags.avoids.includes('strict_latency_sla')) {
        score -= 20;
        reasons.push('avoids_strict_sla');
      }

      // Budget: prefer free providers when budget is tight
      if (budget.maxCostUsd !== undefined && budget.maxCostUsd <= 0) {
        if (provider.kind === 'local' || provider.routing_tags.prefers.includes('free_tier')) {
          score += 10;
          reasons.push('zero_cost_budget');
        }
      }

      scored.push({
        provider_id: pid,
        model_id: model.model_id,
        reason: reasons.join(', '),
        score
      });
    }
  }

  // Sort by score descending
  scored.sort((a, b) => b.score - a.score);

  if (scored.length === 0) {
    explanation.push('No eligible providers found for this request');
  } else {
    explanation.push(`Selected ${scored.length} candidate(s), top: ${scored[0].provider_id}/${scored[0].model_id}`);
  }

  return { candidates: scored, explanation };
}

/**
 * "Explain routing" — human-readable output of routing decision.
 * @param {object} params - Same as routeRequest
 * @returns {string}
 */
function explainRouting(params) {
  const { candidates, explanation } = routeRequest(params);
  const lines = [
    '=== FreeComputeCloud Routing Decision ===',
    `Task class: ${params.taskClass}`,
    `Context length: ${params.contextLength || 'unknown'}`,
    `Latency target: ${params.latencyTarget || 'medium'}`,
    '',
    '--- Explanation ---',
    ...explanation,
    '',
    '--- Candidates (ranked) ---'
  ];

  if (candidates.length === 0) {
    lines.push('  (none)');
  } else {
    for (let i = 0; i < candidates.length; i++) {
      const c = candidates[i];
      lines.push(`  ${i + 1}. ${c.provider_id} / ${c.model_id}  [score=${c.score}]  (${c.reason})`);
    }
  }

  lines.push('=========================================');
  return lines.join('\n');
}

module.exports = { routeRequest, explainRouting };
