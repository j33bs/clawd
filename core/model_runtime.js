const { BACKENDS } = require('./model_constants');
const ModelRouter = require('./router');
const CooldownManager = require('./cooldown_manager');
const GovernanceLogger = require('./governance_logger');
const OathClaudeProvider = require('./providers/oath_claude_provider');
const AnthropicClaudeApiProvider = require('./providers/anthropic_claude_api_provider');
const LiteLlmProxyProvider = require('./providers/litellm_proxy_provider');
const LocalQwenProvider = require('./providers/local_qwen_provider');
const LocalOllamaProvider = require('./providers/local_ollama_provider');
const LocalOpenAiCompatProvider = require('./providers/local_openai_compat_provider');

function isLocalFallbackEnabled(options) {
  if (typeof options.localFallbackEnabled === 'boolean') {
    return options.localFallbackEnabled;
  }
  return String(process.env.OPENCLAW_LOCAL_FALLBACK || '').trim() === '1';
}

function isLiteLlmEnabled(options) {
  if (typeof options.useLiteLlmProxy === 'boolean') {
    return options.useLiteLlmProxy;
  }
  return String(process.env.OPENCLAW_SYSTEM2_USE_LITELLM_PROXY || '').trim() === '1';
}

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

  const localFallbackEnabled = isLocalFallbackEnabled(options);
  const liteLlmEnabled = isLiteLlmEnabled(options);
  const router =
    options.router ||
    new ModelRouter({
      localFallbackEnabled,
      primaryBackends: liteLlmEnabled
        ? [BACKENDS.ANTHROPIC_CLAUDE_API, BACKENDS.OATH_CLAUDE, BACKENDS.LITELLM_PROXY]
        : undefined
    });

  const providers =
    options.providers ||
    (() => {
      const map = {
        [BACKENDS.OATH_CLAUDE]: new OathClaudeProvider({
          cooldownManager,
          invokeFn: options.oathInvokeFn
        }),
        [BACKENDS.ANTHROPIC_CLAUDE_API]: new AnthropicClaudeApiProvider({
          cooldownManager,
          ...options.anthropic
        })
      };

      if (liteLlmEnabled) {
        map[BACKENDS.LITELLM_PROXY] = new LiteLlmProxyProvider({
          ...options.litellm
        });
      }

      if (localFallbackEnabled) {
        map[BACKENDS.LOCAL_OLLAMA] = new LocalOllamaProvider({
          ...options.localOllama
        });
        map[BACKENDS.LOCAL_OPENAI_COMPAT] = new LocalOpenAiCompatProvider({
          ...options.localOpenAiCompat
        });
        map[BACKENDS.LOCAL_QWEN] = new LocalQwenProvider({
          invokeFn: options.qwenInvokeFn
        });
      }

      return map;
    })();

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
