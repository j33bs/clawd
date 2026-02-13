'use strict';

/**
 * FreeComputeCloud — Provider Catalog (v0.1)
 *
 * Data-driven provider inventory. Adding a new provider means adding
 * a catalog entry here — no adapter code changes required for
 * OpenAI-compatible providers.
 *
 * Safety: no secrets. Only env var NAMES and conservative default caps.
 * All numeric quotas are defaults ONLY. Operator must override after
 * verifying account-specific limits.
 */

const CATALOG_VERSION = '0.1';

const CATALOG = Object.freeze([
  // ── LOCAL PROVIDERS (preferred) ──
  {
    provider_id: 'local_vllm',
    kind: 'local',
    protocol: 'openai_compatible',
    enabled_default: false,
    base_url: {
      default: 'http://127.0.0.1:18888/v1',
      env_override: 'OPENCLAW_VLLM_BASE_URL'
    },
    auth: {
      type: 'bearer_optional',
      env_var: 'OPENCLAW_VLLM_API_KEY',
      redact_in_logs: true
    },
    models: [
      {
        model_id: 'AUTO_DISCOVER',
        task_classes: ['fast_chat', 'long_context', 'code', 'batch', 'tool_use'],
        context_window_hint: null,
        tool_support: 'via_adapter',
        notes: 'Replaced with concrete IDs after first successful /v1/models probe.'
      }
    ],
    constraints: {
      quota: {
        mode: 'local_budgeted',
        max_concurrent_requests: { default: 2, env_override: 'OPENCLAW_VLLM_MAX_CONCURRENCY' },
        max_tokens_per_request: { default: 8192, env_override: 'OPENCLAW_VLLM_MAX_TOKENS_PER_REQUEST' }
      },
      backoff: { strategy: 'bounded_exponential', max_retries: 2, cooldown_seconds: 10 },
      circuit_breaker: {
        consecutive_failures_to_open: 3,
        open_seconds: 60,
        half_open_probe_interval_seconds: 30
      }
    },
    healthcheck: {
      type: 'openai_compatible',
      endpoints: { models: '/models', chat: '/chat/completions' },
      timeouts_ms: { connect: 800, read: 6000 },
      probe_prompt: 'Respond with a single word: OK',
      probe_max_tokens: 8
    },
    routing_tags: { prefers: ['local', 'cheap', 'low_latency'], avoids: [] },
    evidence: [
      {
        type: 'doc',
        title: 'vLLM OpenAI-compatible server',
        url: 'https://docs.vllm.ai/en/latest/serving/openai_compatible_server/',
        retrieved_utc: null
      }
    ]
  },

  // ── EXTERNAL "FREE / LOW-COST" PROVIDERS ──
  {
    provider_id: 'gemini',
    kind: 'external',
    protocol: 'vendor_native',
    enabled_default: false,
    base_url: {
      default: 'https://generativelanguage.googleapis.com',
      env_override: 'OPENCLAW_GEMINI_BASE_URL'
    },
    auth: {
      type: 'api_key',
      env_var: 'OPENCLAW_GEMINI_API_KEY',
      redact_in_logs: true
    },
    models: [
      {
        model_id: 'gemini-2.0-flash',
        task_classes: ['fast_chat', 'batch', 'tool_use'],
        context_window_hint: 1048576,
        tool_support: 'native',
        notes: 'Fast/cheap tier. Free tier: 15 RPM, 1M TPM, 1500 RPD.'
      },
      {
        model_id: 'gemini-2.5-pro-preview-05-06',
        task_classes: ['long_context', 'code', 'tool_use'],
        context_window_hint: 1048576,
        tool_support: 'native',
        notes: 'Higher capability. Free tier: 5 RPM, 250K TPM, 25 RPD.'
      }
    ],
    constraints: {
      quota: {
        rpm_default: 10,
        tpm_default: 100000,
        rpd_default: 100,
        tpd_default: 500000,
        reset_policy: 'provider_defined',
        operator_override_required: true
      },
      backoff: { strategy: 'bounded_exponential', max_retries: 2, cooldown_seconds: 20 },
      circuit_breaker: {
        consecutive_failures_to_open: 3,
        open_seconds: 120,
        half_open_probe_interval_seconds: 60
      },
      eligibility: {
        notes: 'Respect region/project eligibility. Do not attempt circumvention.'
      }
    },
    healthcheck: {
      type: 'custom',
      endpoints: { lightweight: '/v1beta/models' },
      timeouts_ms: { connect: 1200, read: 8000 }
    },
    routing_tags: { prefers: ['free_tier', 'fast'], avoids: ['strict_latency_sla'] },
    evidence: [
      {
        type: 'doc',
        title: 'Gemini API rate limits',
        url: 'https://ai.google.dev/gemini-api/docs/rate-limits',
        retrieved_utc: null
      }
    ]
  },

  {
    provider_id: 'groq',
    kind: 'external',
    protocol: 'openai_compatible',
    enabled_default: false,
    base_url: {
      default: 'https://api.groq.com/openai/v1',
      env_override: 'OPENCLAW_GROQ_BASE_URL'
    },
    auth: {
      type: 'bearer',
      env_var: 'OPENCLAW_GROQ_API_KEY',
      alias_env_vars: ['GROQ_API_KEY'],
      redact_in_logs: true
    },
    models: [
      {
        model_id: 'llama-3.3-70b-versatile',
        task_classes: ['fast_chat', 'code', 'tool_use'],
        context_window_hint: 131072,
        tool_support: 'via_adapter',
        notes: 'Verify via /models. Free tier: 30 RPM, 15K TPM, 14.4K RPD.'
      },
      {
        model_id: 'mixtral-8x7b-32768',
        task_classes: ['long_context', 'batch'],
        context_window_hint: 32768,
        tool_support: 'via_adapter',
        notes: 'Verify availability.'
      }
    ],
    constraints: {
      quota: {
        rpm_default: 10,
        tpm_default: 200000,
        rpd_default: 200,
        tpd_default: 1000000,
        reset_policy: 'provider_defined',
        operator_override_required: true
      },
      backoff: { strategy: 'bounded_exponential', max_retries: 2, cooldown_seconds: 15 },
      circuit_breaker: {
        consecutive_failures_to_open: 3,
        open_seconds: 90,
        half_open_probe_interval_seconds: 45
      }
    },
    healthcheck: {
      type: 'openai_compatible',
      endpoints: { models: '/models', chat: '/chat/completions' },
      timeouts_ms: { connect: 800, read: 7000 },
      probe_prompt: 'Reply with: OK',
      probe_max_tokens: 8
    },
    routing_tags: { prefers: ['low_latency', 'burst_capacity'], avoids: [] },
    evidence: [
      {
        type: 'doc',
        title: 'Groq rate limits',
        url: 'https://console.groq.com/docs/rate-limits',
        retrieved_utc: null
      }
    ]
  },

  {
    provider_id: 'qwen_alibaba',
    kind: 'external',
    protocol: 'openai_compatible',
    enabled_default: false,
    base_url: {
      default: 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1',
      env_override: 'OPENCLAW_QWEN_BASE_URL'
    },
    auth: {
      type: 'bearer',
      env_var: 'OPENCLAW_QWEN_API_KEY',
      redact_in_logs: true
    },
    models: [
      {
        model_id: 'qwen-plus',
        task_classes: ['long_context', 'code', 'batch'],
        context_window_hint: 131072,
        tool_support: 'via_adapter',
        notes: 'Verify IDs and free quota in your console. 1M free tokens for new accounts.'
      },
      {
        model_id: 'qwen-turbo',
        task_classes: ['fast_chat', 'code', 'tool_use'],
        context_window_hint: 131072,
        tool_support: 'via_adapter',
        notes: 'Verify IDs and free quota.'
      }
    ],
    constraints: {
      quota: {
        mode: 'free_quota_preferred',
        rpm_default: 5,
        tpm_default: 80000,
        rpd_default: 50,
        tpd_default: 400000,
        reset_policy: 'provider_defined',
        operator_override_required: true
      },
      billing_safety: {
        require_free_quota_only_flag: true,
        notes: 'Operator must enable provider-side protection against paid usage where supported.'
      },
      backoff: { strategy: 'bounded_exponential', max_retries: 2, cooldown_seconds: 25 },
      circuit_breaker: {
        consecutive_failures_to_open: 3,
        open_seconds: 180,
        half_open_probe_interval_seconds: 90
      },
      eligibility: {
        notes: 'Region (intl vs mainland) matters. Respect eligibility; no workarounds.'
      }
    },
    healthcheck: {
      type: 'openai_compatible',
      endpoints: { models: '/models', chat: '/chat/completions' },
      timeouts_ms: { connect: 1200, read: 9000 }
    },
    routing_tags: { prefers: ['free_tier', 'high_capability'], avoids: [] },
    evidence: [
      {
        type: 'doc',
        title: 'Model Studio free quota (Intl edition)',
        url: 'https://www.alibabacloud.com/help/en/model-studio/new-free-quota',
        retrieved_utc: null
      }
    ]
  },

  // ── PAID FALLBACK PROVIDERS ──
  {
    provider_id: 'openai',
    kind: 'external',
    protocol: 'openai_compatible',
    enabled_default: false,
    base_url: {
      default: 'https://api.openai.com/v1',
      env_override: 'OPENCLAW_OPENAI_BASE_URL'
    },
    auth: {
      type: 'bearer',
      env_var: 'OPENCLAW_OPENAI_API_KEY',
      alias_env_vars: ['OPENAI_API_KEY'],
      redact_in_logs: true
    },
    models: [
      {
        model_id: 'gpt-5-chat-latest',
        task_classes: ['fast_chat', 'long_context', 'tool_use', 'batch'],
        context_window_hint: null,
        tool_support: 'via_adapter',
        notes: 'Paid chat fallback. Operator must configure spend protections and limits.'
      },
      {
        model_id: 'gpt-5-mini',
        task_classes: ['fast_chat', 'tool_use', 'batch', 'code'],
        context_window_hint: null,
        tool_support: 'via_adapter',
        notes: 'Paid chat fallback (cheaper). Operator must configure spend protections and limits.'
      },
      {
        model_id: 'gpt-5-codex',
        task_classes: ['code', 'tool_use'],
        context_window_hint: null,
        tool_support: 'via_adapter',
        notes: 'Paid coding/tool fallback (may require explicit enable; see FREECOMPUTE_OPENAI_CODEX_MODEL).'
      }
    ],
    constraints: {
      quota: {
        rpm_default: 5,
        rpd_default: 50,
        tpm_default: 60000,
        tpd_default: 300000,
        reset_policy: 'provider_defined',
        operator_override_required: true
      },
      billing_safety: {
        notes: 'Paid provider. Enable provider-side billing protections and enforce operator budgets.'
      },
      backoff: { strategy: 'bounded_exponential', max_retries: 1, cooldown_seconds: 10 },
      circuit_breaker: {
        consecutive_failures_to_open: 2,
        open_seconds: 180,
        half_open_probe_interval_seconds: 60
      }
    },
    healthcheck: {
      type: 'openai_compatible',
      endpoints: { models: '/models', chat: '/chat/completions' },
      timeouts_ms: { connect: 900, read: 9000 },
      probe_prompt: 'Reply with: OK',
      probe_max_tokens: 8
    },
    routing_tags: { prefers: ['paid_fallback'], avoids: [] },
    evidence: [
      {
        type: 'doc',
        title: 'OpenAI API',
        url: 'https://platform.openai.com/docs',
        retrieved_utc: null
      }
    ]
  },

  {
    provider_id: 'openrouter',
    kind: 'external',
    protocol: 'openai_compatible',
    enabled_default: false,
    base_url: {
      default: 'https://openrouter.ai/api/v1',
      env_override: 'OPENCLAW_OPENROUTER_BASE_URL'
    },
    auth: {
      type: 'bearer',
      env_var: 'OPENCLAW_OPENROUTER_API_KEY',
      redact_in_logs: true
    },
    models: [
      {
        model_id: 'qwen/qwen-2.5-72b-instruct:free',
        task_classes: ['long_context', 'code', 'batch'],
        context_window_hint: 131072,
        tool_support: 'via_adapter',
        notes: 'Free variant. Availability changes frequently.'
      },
      {
        model_id: 'meta-llama/llama-3.3-70b-instruct:free',
        task_classes: ['fast_chat', 'code'],
        context_window_hint: 131072,
        tool_support: 'via_adapter',
        notes: 'Free variant. Availability changes frequently.'
      }
    ],
    constraints: {
      quota: {
        rpm_default: 20,
        rpd_default: 50,
        tpm_default: 80000,
        tpd_default: 400000,
        reset_policy: 'provider_defined',
        operator_override_required: false
      },
      backoff: { strategy: 'bounded_exponential', max_retries: 2, cooldown_seconds: 30 },
      circuit_breaker: {
        consecutive_failures_to_open: 3,
        open_seconds: 120,
        half_open_probe_interval_seconds: 60
      }
    },
    healthcheck: {
      type: 'openai_compatible',
      endpoints: { models: '/models', chat: '/chat/completions' },
      timeouts_ms: { connect: 900, read: 9000 },
      probe_prompt: 'Reply with: OK',
      probe_max_tokens: 8
    },
    routing_tags: { prefers: ['free_tier', 'model_variety'], avoids: ['stable_sla'] },
    evidence: [
      {
        type: 'doc',
        title: 'OpenRouter limits',
        url: 'https://openrouter.ai/docs/api/reference/limits',
        retrieved_utc: null
      }
    ]
  }
]);

/**
 * Look up a catalog entry by provider_id.
 * @param {string} providerId
 * @returns {object|null}
 */
function getProvider(providerId) {
  return CATALOG.find((p) => p.provider_id === providerId) || null;
}

/**
 * Get all providers matching a filter.
 * @param {object} [filter] - { kind, taskClass, tag }
 * @returns {object[]}
 */
function queryProviders(filter = {}) {
  let result = [...CATALOG];
  if (filter.kind) {
    result = result.filter((p) => p.kind === filter.kind);
  }
  if (filter.taskClass) {
    result = result.filter((p) =>
      p.models.some((m) => m.task_classes.includes(filter.taskClass))
    );
  }
  if (filter.tag) {
    result = result.filter((p) =>
      p.routing_tags.prefers.includes(filter.tag)
    );
  }
  return result;
}

module.exports = {
  CATALOG_VERSION,
  CATALOG,
  getProvider,
  queryProviders
};
