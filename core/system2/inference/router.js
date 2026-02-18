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

const TIER = Object.freeze({
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high'
});

function inferArousalTier(taskInput) {
  const text = String(taskInput || '');
  if (!text.trim()) return TIER.MEDIUM;
  const lower = text.toLowerCase();

  let score = 0;
  const tokens = text.trim().split(/\s+/).filter(Boolean).length;
  if (tokens > 40) score += 0.12;
  if (tokens > 120) score += 0.14;
  if (tokens > 250) score += 0.18;
  if ((text.match(/\n/g) || []).length + 1 > 10) score += 0.08;
  if (text.includes('```') || lower.includes('traceback') || lower.includes('stack trace')) score += 0.14;
  if (/\b(must|non-negotiable|constraint|gate|fail-closed)\b/.test(lower)) score += 0.10;
  const keywordHits = (lower.match(/\b(analyze|audit|architecture|debug|failure|incident|security|traceback|regression|integration|routing|verify|cross-timescale)\b/g) || []).length;
  if (keywordHits > 0) score += Math.min(0.32, keywordHits * 0.05);

  if (score <= 0.33) return TIER.LOW;
  if (score <= 0.66) return TIER.MEDIUM;
  return TIER.HIGH;
}

/**
 * Route a request to the best available provider(s).
 *
 * @param {object} params
 * @param {string} params.taskClass       - One of REQUEST_CLASSES
 * @param {number} [params.contextLength] - Estimated input token count
 * @param {string} [params.latencyTarget] - 'low' | 'medium' | 'high'
 * @param {string} [params.taskInput]     - Flattened request text for tiering
 * @param {'low'|'medium'|'high'} [params.recommendedTier] - Precomputed arousal tier
 * @param {object} [params.budget]        - { maxCostUsd, maxTokens }
 * @param {object} params.providerHealth  - { provider_id → { ok: boolean } }
 * @param {object} params.quotaState      - { provider_id → { allowed: boolean, reason? } }
 * @param {object} params.config          - Output of loadFreeComputeConfig()
 * @param {string[]} [params.availableProviderIds] - Optional: restrict routing to providers with adapters
 * @returns {{ candidates: Array<{ provider_id, model_id, reason, score }>, explanation: string[] }}
 */
function routeRequest(params) {
  const {
    taskClass,
    contextLength = 0,
    latencyTarget = 'medium',
    taskInput = '',
    recommendedTier = null,
    budget = {},
    providerHealth = {},
    quotaState = {},
    config,
    availableProviderIds
  } = params;

  const cloudEnabled = Boolean(config && config.enabled);
  const localEnabled = Boolean(config && config.vllmEnabled);
  const tactiCrRoutingEnabled = Boolean(config && config.tactiCrRoutingEnabled);
  const resolvedTier = tactiCrRoutingEnabled
    ? (recommendedTier || inferArousalTier(taskInput))
    : null;

  // Cloud/free tiers are gated behind ENABLE_FREECOMPUTE_CLOUD (or alias),
  // but local vLLM remains a safe escape hatch even when cloud is disabled.
  if (!config || (!cloudEnabled && !localEnabled)) {
    return {
      candidates: [],
      explanation: ['FreeComputeCloud is disabled (ENABLE_FREECOMPUTE_CLOUD=0 and ENABLE_FREECOMPUTE=0) and local vLLM is disabled (ENABLE_LOCAL_VLLM=0)']
    };
  }

  const explanation = [];
  const scored = [];
  const available = Array.isArray(availableProviderIds) ? new Set(availableProviderIds) : null;

  for (const provider of CATALOG) {
    const pid = provider.provider_id;

    // Operator policy: OpenAI/Codex API automation is disabled for now.
    if (pid.startsWith('openai')) {
      explanation.push(`${pid}: skipped (operator disabled; no API automation)`);
      continue;
    }

    // Cloud-disabled mode: only consider local providers (escape hatch).
    if (provider.kind === 'external' && !cloudEnabled) {
      explanation.push(`${pid}: skipped (cloud disabled; set ENABLE_FREECOMPUTE_CLOUD=1 or ENABLE_FREECOMPUTE=1)`);
      continue;
    }

    // If a registry provided the concrete adapter set, don't emit candidates for absent adapters.
    if (available && !available.has(pid)) {
      explanation.push(`${pid}: skipped (no adapter / not configured)`);
      continue;
    }

    // ── Feature flag gate ──
    if (pid === 'local_vllm' && !localEnabled) {
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
    let matchingModels = provider.models.filter((m) =>
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
        // Local is an escape hatch. When cloud is enabled, prefer free cloud first.
        // When cloud is disabled, local should be preferred.
        if (!cloudEnabled) {
          score += 100;
          reasons.push('local_preferred_cloud_disabled');
        } else {
          score += 0;
          reasons.push('local_fallback_cloud_enabled');
        }
      }

      // Paid providers are fallback-only unless no free/local options remain.
      if (provider.routing_tags.prefers.includes('paid_fallback')) {
        score -= 50;
        reasons.push('paid_fallback');
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

      // Optional TACTI(C)-R arousal modulation (default-off).
      if (resolvedTier === TIER.LOW) {
        if (provider.kind === 'local') {
          score += 70;
          reasons.push('tacti_cr_low_local_preferred');
        } else {
          score -= 10;
          reasons.push('tacti_cr_low_external_penalty');
        }
        if (provider.routing_tags.prefers.includes('low_latency') || provider.routing_tags.prefers.includes('fast')) {
          score += 15;
          reasons.push('tacti_cr_low_fast_preferred');
        }
      } else if (resolvedTier === TIER.HIGH) {
        if (provider.kind === 'local') {
          score -= 40;
          reasons.push('tacti_cr_high_deprioritize_local');
        }
        if (provider.routing_tags.prefers.includes('high_capability')) {
          score += 35;
          reasons.push('tacti_cr_high_capability');
        }
        if ((model.context_window_hint || 0) >= 100000) {
          score += 20;
          reasons.push('tacti_cr_high_context_window');
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

  // Sort by score desc, then deterministic tie-break (provider_id, model_id).
  scored.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    if (a.provider_id !== b.provider_id) return a.provider_id.localeCompare(b.provider_id);
    return a.model_id.localeCompare(b.model_id);
  });

  // Hard escape hatch: if local_vllm is available+healthy, never return empty.
  if (scored.length === 0 && localEnabled && (!available || available.has('local_vllm'))) {
    const h = providerHealth.local_vllm;
    const q = quotaState.local_vllm;
    const healthy = !h || h.ok;
    const quotaOk = !q || q.allowed;
    if (healthy && quotaOk) {
      scored.push({
        provider_id: 'local_vllm',
        model_id: 'AUTO_DISCOVER',
        reason: 'escape_hatch_local_vllm',
        score: 1000
      });
      explanation.push('escape_hatch_local_vllm: injected local_vllm as final fallback');
    }
  }

  if (scored.length === 0) {
    explanation.push('No eligible providers found for this request');
  } else {
    explanation.push(`Selected ${scored.length} candidate(s), top: ${scored[0].provider_id}/${scored[0].model_id}`);
    if (resolvedTier) {
      explanation.push(`TACTI(C)-R tier=${resolvedTier}`);
    }
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
