const { BACKENDS, TASK_CLASSES } = require('./model_constants');

const BASIC_HINTS = [
  'grep',
  'search',
  'find',
  'list',
  'ls',
  'format',
  'lint',
  'docs',
  'readme',
  'small refactor',
  'summarize local',
  'run tests',
  'build'
];

const NON_BASIC_HINTS = [
  'architecture',
  'governance',
  'invariant',
  'multi-file',
  'complex debug',
  'deep reasoning',
  'requires_claude'
];

const PRIMARY_BACKENDS = [BACKENDS.ANTHROPIC_CLAUDE_API, BACKENDS.OATH_CLAUDE];
const LOCAL_BACKENDS = [
  BACKENDS.LOCAL_OLLAMA,
  BACKENDS.LOCAL_OPENAI_COMPAT,
  BACKENDS.LOCAL_QWEN
];

function normalizeTaskClass(value) {
  if (!value) {
    return null;
  }
  const normalized = String(value).toUpperCase();
  if (normalized === TASK_CLASSES.BASIC) {
    return TASK_CLASSES.BASIC;
  }
  if (normalized === TASK_CLASSES.NON_BASIC || normalized === 'NON-BASIC') {
    return TASK_CLASSES.NON_BASIC;
  }
  return null;
}

function flagEnabled(value) {
  return String(value || '').trim() === '1';
}

class ModelRouter {
  constructor(options = {}) {
    this.primaryBackends = Array.isArray(options.primaryBackends) && options.primaryBackends.length > 0
      ? [...options.primaryBackends]
      : [...PRIMARY_BACKENDS];
    this.localBackends = Array.isArray(options.localBackends) && options.localBackends.length > 0
      ? [...options.localBackends]
      : [...LOCAL_BACKENDS];
    this.localFallbackEnabled =
      typeof options.localFallbackEnabled === 'boolean'
        ? options.localFallbackEnabled
        : flagEnabled(process.env.OPENCLAW_LOCAL_FALLBACK);
  }

  resolveTaskClass(taskClass, metadata = {}, messages = []) {
    const explicit =
      normalizeTaskClass(taskClass) ||
      normalizeTaskClass(metadata.taskClass) ||
      normalizeTaskClass(metadata.task_class);

    if (explicit) {
      return explicit;
    }

    const text = [
      metadata.task_name || '',
      ...messages.map((m) => (typeof m.content === 'string' ? m.content : ''))
    ]
      .join(' ')
      .toLowerCase();

    if (NON_BASIC_HINTS.some((hint) => text.includes(hint))) {
      return TASK_CLASSES.NON_BASIC;
    }

    if (BASIC_HINTS.some((hint) => text.includes(hint))) {
      return TASK_CLASSES.BASIC;
    }

    return TASK_CLASSES.BASIC;
  }

  localCandidates() {
    return this.localFallbackEnabled ? [...this.localBackends] : [];
  }

  isLocalBackend(backend) {
    return this.localBackends.includes(backend);
  }

  buildRoutePlan({
    taskClass,
    requiresClaude = false,
    allowNetwork = true,
    preferredBackend = null,
    metadata = {},
    messages = []
  }) {
    const resolvedTaskClass = this.resolveTaskClass(taskClass, metadata, messages);
    const localCandidates = this.localCandidates();

    let candidates;
    if (allowNetwork === false) {
      candidates = localCandidates;
    } else {
      candidates = [...this.primaryBackends, ...localCandidates];
    }

    const defaultPreferred =
      allowNetwork === false
        ? localCandidates[0] || null
        : this.primaryBackends[0] || null;

    const requestedPreferred = Object.values(BACKENDS).includes(preferredBackend)
      ? preferredBackend
      : null;

    const canPreferLocal = allowNetwork === false;

    if (
      requestedPreferred &&
      !candidates.includes(requestedPreferred) &&
      (canPreferLocal || !this.isLocalBackend(requestedPreferred))
    ) {
      candidates = [requestedPreferred, ...candidates];
    }

    // Advisory only and policy-compatible.
    if (
      requestedPreferred &&
      candidates.includes(requestedPreferred) &&
      (canPreferLocal || !this.isLocalBackend(requestedPreferred))
    ) {
      candidates = [requestedPreferred, ...candidates.filter((c) => c !== requestedPreferred)];
    }

    return {
      taskClass: resolvedTaskClass,
      requiresClaude: Boolean(requiresClaude),
      allowNetwork: allowNetwork !== false,
      preferredBackend: requestedPreferred || defaultPreferred,
      candidates
    };
  }

  cooldownKeyForBackend(backend) {
    if (backend === BACKENDS.OATH_CLAUDE) {
      return 'oath';
    }
    if (backend === BACKENDS.ANTHROPIC_CLAUDE_API) {
      return 'anthropic';
    }
    return null;
  }

  networkUsedForBackend(backend) {
    return !this.isLocalBackend(backend);
  }
}

module.exports = ModelRouter;
