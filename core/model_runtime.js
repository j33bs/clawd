const { BACKENDS } = require('./model_constants');
const ModelRouter = require('./router');
const CooldownManager = require('./cooldown_manager');
const GovernanceLogger = require('./governance_logger');
const OathClaudeProvider = require('./providers/oath_claude_provider');
const AnthropicClaudeApiProvider = require('./providers/anthropic_claude_api_provider');
const LocalQwenProvider = require('./providers/local_qwen_provider');

function createModelRuntime(options = {}) {
  const cooldownManager =
    options.cooldownManager ||
    new CooldownManager({
      cooldownMinutes: options.cooldownMinutes,
      timeoutWindowMinutes: options.timeoutWindowMinutes,
      timeoutStrikes: options.timeoutStrikes
    });

  const logger =
    options.logger ||
    new GovernanceLogger({
      persist: options.persistLogs !== false
    });

  const router = options.router || new ModelRouter();

  const providers =
    options.providers ||
    {
      [BACKENDS.OATH_CLAUDE]: new OathClaudeProvider({
        cooldownManager,
        invokeFn: options.oathInvokeFn
      }),
      [BACKENDS.ANTHROPIC_CLAUDE_API]: new AnthropicClaudeApiProvider({
        cooldownManager,
        ...options.anthropic
      }),
      [BACKENDS.LOCAL_QWEN]: new LocalQwenProvider({
        invokeFn: options.qwenInvokeFn
      })
    };

  return {
    router,
    cooldownManager,
    logger,
    providers
  };
}

module.exports = {
  createModelRuntime
};
