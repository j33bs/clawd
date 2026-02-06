class LocalQwenProvider {
  constructor(options = {}) {
    this.invokeFn = options.invokeFn || null;
  }

  async health() {
    return { ok: true };
  }

  async call({ messages = [], metadata = {} }) {
    const simulation = metadata && metadata.simulation ? metadata.simulation : {};

    if (simulation.qwenError) {
      const simulated = new Error(`Simulated Qwen error: ${simulation.qwenError}`);
      simulated.code = simulation.qwenError;
      throw simulated;
    }

    const invoke = this.invokeFn || global.__OPENCLAW_QWEN_CALL;
    if (typeof invoke === 'function') {
      return invoke({ messages, metadata });
    }

    const lastUser = [...messages].reverse().find((m) => m.role === 'user');
    const text = typeof lastUser?.content === 'string' ? lastUser.content : '';

    return {
      text: text ? `Local Qwen processed: ${text}` : 'Local Qwen processed request.',
      raw: { provider: 'local_qwen', simulated: true },
      usage: {
        inputTokens: Math.ceil(JSON.stringify(messages).length / 4),
        outputTokens: 24,
        totalTokens: Math.ceil(JSON.stringify(messages).length / 4) + 24,
        estimatedCostUsd: 0
      }
    };
  }
}

module.exports = LocalQwenProvider;
