const { normalizeProviderError } = require('../normalize_error');

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function normalizeMessageContent(content) {
  if (typeof content === 'string') {
    return content;
  }
  if (Array.isArray(content)) {
    return content
      .map((item) => {
        if (typeof item === 'string') {
          return item;
        }
        if (item && typeof item.text === 'string') {
          return item.text;
        }
        return '';
      })
      .join('\n');
  }
  return '';
}

function mapMessages(messages) {
  const systemParts = [];
  const mapped = [];

  messages.forEach((message) => {
    const role = String(message.role || 'user').toLowerCase();
    const content = normalizeMessageContent(message.content);

    if (role === 'system') {
      if (content) {
        systemParts.push(content);
      }
      return;
    }

    mapped.push({
      role: role === 'assistant' ? 'assistant' : 'user',
      content
    });
  });

  return {
    system: systemParts.join('\n\n').trim() || null,
    messages: mapped.length > 0 ? mapped : [{ role: 'user', content: '' }]
  };
}

class AnthropicClaudeApiProvider {
  constructor(options = {}) {
    this.baseUrl = options.baseUrl || 'https://api.anthropic.com/v1/messages';
    this.apiVersion = options.apiVersion || process.env.ANTHROPIC_VERSION || '2023-06-01';
    this.defaultModel = options.defaultModel || process.env.ANTHROPIC_MODEL || 'claude-3-5-sonnet-latest';
    this.retryCount = Number(options.retryCount ?? 2);
    this.timeoutMs = Number(options.timeoutMs ?? process.env.ANTHROPIC_TIMEOUT_MS ?? 30000);
    this.cooldownManager = options.cooldownManager || null;
  }

  hasApiKey(metadata = {}) {
    return Boolean(metadata.anthropicApiKey || process.env.ANTHROPIC_API_KEY);
  }

  async health({ metadata = {} } = {}) {
    if (this.cooldownManager && this.cooldownManager.isDisabled('anthropic')) {
      return { ok: false, reason: 'cooldown' };
    }
    if (!this.hasApiKey(metadata)) {
      return { ok: false, reason: 'missing_api_key' };
    }
    return { ok: true };
  }

  async call({ messages = [], metadata = {}, allowNetwork = true }) {
    const simulation = metadata && metadata.simulation ? metadata.simulation : {};

    if (simulation.anthropicError) {
      const simulated = new Error(`Simulated Anthropic error: ${simulation.anthropicError}`);
      simulated.code = simulation.anthropicError;
      if (simulation.anthropicStatus) {
        simulated.status = simulation.anthropicStatus;
      }
      throw simulated;
    }

    if (simulation.anthropicSuccess) {
      return {
        text: 'Simulated Anthropic success',
        raw: { provider: 'anthropic', simulated: true },
        usage: {
          inputTokens: 10,
          outputTokens: 12,
          totalTokens: 22,
          estimatedCostUsd: null
        }
      };
    }

    if (!allowNetwork) {
      const error = new Error('Network is disabled for Anthropic provider');
      error.code = 'NETWORK_DISABLED';
      throw error;
    }

    const apiKey = metadata.anthropicApiKey || process.env.ANTHROPIC_API_KEY;
    if (!apiKey) {
      const error = new Error('ANTHROPIC_API_KEY is missing');
      error.status = 401;
      error.code = 'MISSING_API_KEY';
      throw error;
    }

    const mapped = mapMessages(messages);
    const model = metadata.anthropicModel || process.env.ANTHROPIC_MODEL || this.defaultModel;
    const maxTokens = Number(metadata.maxTokens || 1024);

    const body = {
      model,
      max_tokens: maxTokens,
      messages: mapped.messages
    };

    if (mapped.system) {
      body.system = mapped.system;
    }

    let lastError = null;

    for (let attempt = 0; attempt <= this.retryCount; attempt += 1) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), this.timeoutMs);

      try {
        const response = await fetch(this.baseUrl, {
          method: 'POST',
          headers: {
            'content-type': 'application/json',
            'x-api-key': apiKey,
            'anthropic-version': this.apiVersion
          },
          body: JSON.stringify(body),
          signal: controller.signal
        });

        clearTimeout(timer);

        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          const error = new Error(payload?.error?.message || `Anthropic request failed: ${response.status}`);
          error.status = response.status;
          error.code = payload?.error?.type || null;
          error.body = payload;
          throw error;
        }

        const text = Array.isArray(payload.content)
          ? payload.content
              .filter((item) => item && item.type === 'text' && typeof item.text === 'string')
              .map((item) => item.text)
              .join('\n')
          : '';

        const usage = payload.usage || {};

        return {
          text,
          raw: payload,
          usage: {
            inputTokens: usage.input_tokens || 0,
            outputTokens: usage.output_tokens || 0,
            totalTokens: (usage.input_tokens || 0) + (usage.output_tokens || 0),
            estimatedCostUsd: null
          }
        };
      } catch (error) {
        clearTimeout(timer);

        const normalized = normalizeProviderError(error, 'ANTHROPIC_CLAUDE_API');
        lastError = error;

        const retryable = normalized.code === 'TIMEOUT' || normalized.code === 'RATE_LIMIT';
        if (!retryable || attempt >= this.retryCount) {
          throw error;
        }

        await sleep(250 * Math.pow(2, attempt));
      }
    }

    throw lastError || new Error('Anthropic request failed');
  }
}

module.exports = AnthropicClaudeApiProvider;
