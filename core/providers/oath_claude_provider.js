class OathClaudeProvider {
  constructor(options = {}) {
    this.invokeFn = options.invokeFn || null;
    this.cooldownManager = options.cooldownManager || null;
  }

  async health() {
    if (this.cooldownManager && this.cooldownManager.isDisabled('oath')) {
      return { ok: false, reason: 'cooldown' };
    }
    return { ok: true };
  }

  async call({ messages = [], metadata = {} }) {
    const simulation = metadata && metadata.simulation ? metadata.simulation : {};

    if (simulation.oathError) {
      const simulated = new Error(`Simulated Oath error: ${simulation.oathError}`);
      simulated.code = simulation.oathError;
      if (simulation.oathStatus) {
        simulated.status = simulation.oathStatus;
      }
      throw simulated;
    }

    const invoke = this.invokeFn || global.__OPENCLAW_OATH_CALL;
    if (typeof invoke === 'function') {
      return invoke({ messages, metadata });
    }

    const lastUser = [...messages].reverse().find((m) => m.role === 'user');
    const text = typeof lastUser?.content === 'string' ? lastUser.content : '';

    return {
      text: text ? `Oath Claude processed: ${text}` : 'Oath Claude processed request.',
      raw: { provider: 'oath_claude', simulated: true },
      usage: {
        inputTokens: Math.ceil(JSON.stringify(messages).length / 4),
        outputTokens: 32,
        totalTokens: Math.ceil(JSON.stringify(messages).length / 4) + 32,
        estimatedCostUsd: null
      }
    };
  }
}

module.exports = OathClaudeProvider;
