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

class ModelRouter {
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

  buildRoutePlan({
    taskClass,
    requiresClaude = false,
    allowNetwork = true,
    preferredBackend = null,
    metadata = {},
    messages = []
  }) {
    const resolvedTaskClass = this.resolveTaskClass(taskClass, metadata, messages);

    let candidates;
    if (allowNetwork === false) {
      candidates = [BACKENDS.LOCAL_QWEN];
    } else if (resolvedTaskClass === TASK_CLASSES.BASIC && !requiresClaude) {
      candidates = [BACKENDS.LOCAL_QWEN];
    } else {
      candidates = [BACKENDS.OATH_CLAUDE, BACKENDS.ANTHROPIC_CLAUDE_API, BACKENDS.LOCAL_QWEN];
    }

    const defaultPreferred =
      resolvedTaskClass === TASK_CLASSES.BASIC && !requiresClaude
        ? BACKENDS.LOCAL_QWEN
        : BACKENDS.OATH_CLAUDE;

    const requestedPreferred = Object.values(BACKENDS).includes(preferredBackend)
      ? preferredBackend
      : null;

    // Advisory only and policy-compatible.
    if (
      requestedPreferred &&
      candidates.includes(requestedPreferred) &&
      !(resolvedTaskClass === TASK_CLASSES.BASIC && !requiresClaude && requestedPreferred !== BACKENDS.LOCAL_QWEN)
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
    return backend !== BACKENDS.LOCAL_QWEN;
  }
}

module.exports = ModelRouter;
