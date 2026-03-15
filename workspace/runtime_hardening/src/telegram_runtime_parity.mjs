import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function collectTelegramPolicyTargets(policy) {
  const routing = policy?.routing || {};
  const providers = policy?.providers || {};
  const telegramProfile = routing?.surface_profiles?.telegram || {};
  const conversationOrder = telegramProfile?.intents?.conversation?.order || [];
  const capabilityRouter = telegramProfile?.capability_router || {};

  const providerOrder = [];
  const seen = new Set();
  for (const provider of [
    ...conversationOrder,
    capabilityRouter.chatProvider,
    capabilityRouter.planningProvider,
    capabilityRouter.reasoningProvider,
    capabilityRouter.codeProvider,
    capabilityRouter.smallCodeProvider
  ]) {
    const normalized = typeof provider === 'string' ? provider.trim() : '';
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    providerOrder.push(normalized);
  }

  return providerOrder.map((provider) => ({
    provider,
    models: Array.isArray(providers?.[provider]?.models)
      ? providers[provider].models
          .map((entry) => (typeof entry?.id === 'string' ? entry.id.trim() : ''))
          .filter(Boolean)
      : []
  }));
}

function collectRuntimeProviders(runtimeConfig) {
  return runtimeConfig?.models?.providers || {};
}

function normalizeModelId(value) {
  const raw = typeof value === 'string' ? value.trim() : '';
  if (!raw) return '';
  if (raw.startsWith('minimax-portal/')) {
    return raw.slice('minimax-portal/'.length);
  }
  return raw;
}

function compareTelegramRuntimeParity({ policy, runtimeConfig }) {
  const targets = collectTelegramPolicyTargets(policy);
  const runtimeProviders = collectRuntimeProviders(runtimeConfig);
  const runtimeModelIndex = new Map();

  for (const [providerName, providerCfg] of Object.entries(runtimeProviders)) {
    const runtimeModels = Array.isArray(providerCfg?.models) ? providerCfg.models : [];
    for (const model of runtimeModels) {
      const rawModelId = typeof model?.id === 'string' ? model.id.trim() : '';
      const normalizedModelId = normalizeModelId(rawModelId);
      if (!normalizedModelId) continue;
      if (!runtimeModelIndex.has(normalizedModelId)) {
        runtimeModelIndex.set(normalizedModelId, []);
      }
      runtimeModelIndex.get(normalizedModelId).push({
        provider: providerName,
        model: rawModelId
      });
    }
  }

  const providers = targets.map((target) => {
    const runtimeProvider = runtimeProviders[target.provider];
    const runtimeModelIds = Array.isArray(runtimeProvider?.models)
      ? runtimeProvider.models
          .map((entry) => (typeof entry?.id === 'string' ? entry.id.trim() : ''))
          .filter(Boolean)
      : [];
    const matchingProviders = new Set();
    const matchingModels = [];
    for (const modelId of target.models) {
      const matches = runtimeModelIndex.get(normalizeModelId(modelId)) || [];
      if (matches.length === 0) continue;
      matchingModels.push(modelId);
      for (const match of matches) {
        matchingProviders.add(match.provider);
      }
    }
    return {
      provider: target.provider,
      required_models: target.models,
      runtime_present: Boolean(runtimeProvider) || matchingProviders.size > 0,
      runtime_models: runtimeModelIds,
      runtime_matching_providers: Array.from(matchingProviders).sort(),
      matching_models: matchingModels,
      status:
        !(Boolean(runtimeProvider) || matchingProviders.size > 0)
          ? 'missing_provider'
          : target.models.length > 0 && matchingModels.length === 0
            ? 'missing_models'
            : 'ok'
    };
  });

  const mismatches = providers.filter((provider) => provider.status !== 'ok');
  return {
    surface: 'telegram',
    policy_profile: 'surface:telegram',
    status: mismatches.length === 0 ? 'ok' : 'mismatch',
    providers,
    mismatches
  };
}

function resolveDefaultPaths(repoRoot) {
  return {
    policyPath: path.join(repoRoot, 'workspace', 'policy', 'llm_policy.json'),
    runtimeConfigPath: path.join(process.env.HOME || '~', '.openclaw', 'openclaw.json')
  };
}

function verifyTelegramRuntimeParity({
  repoRoot,
  policyPath,
  runtimeConfigPath
} = {}) {
  const defaults = resolveDefaultPaths(repoRoot || process.cwd());
  const resolvedPolicyPath = policyPath || defaults.policyPath;
  const resolvedRuntimeConfigPath = runtimeConfigPath || defaults.runtimeConfigPath;

  return compareTelegramRuntimeParity({
    policy: readJson(resolvedPolicyPath),
    runtimeConfig: readJson(resolvedRuntimeConfigPath)
  });
}

function main(argv = process.argv.slice(2)) {
  const repoRoot = argv[0] ? path.resolve(argv[0]) : process.cwd();
  const result = verifyTelegramRuntimeParity({ repoRoot });
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  return result.status === 'ok' ? 0 : 1;
}

const invokedPath = process.argv[1] ? pathToFileURL(path.resolve(process.argv[1])).href : null;
if (invokedPath && import.meta.url === invokedPath) {
  process.exitCode = main();
}

export {
  collectRuntimeProviders,
  collectTelegramPolicyTargets,
  compareTelegramRuntimeParity,
  resolveDefaultPaths,
  verifyTelegramRuntimeParity
};
