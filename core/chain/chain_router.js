const PROFILE_ORDER = ['reasoning_remote', 'code_remote', 'cheap_transform'];

function normalizeIntent(intent) {
  return String(intent || '').toLowerCase();
}

function profileForIntent(intent) {
  const value = normalizeIntent(intent);
  if (
    value.includes('format') ||
    value.includes('rewrite') ||
    value.includes('summarize') ||
    value.includes('extract') ||
    value.includes('classify') ||
    value.includes('normalize')
  ) {
    return 'cheap_transform';
  }
  if (
    value.includes('refactor') ||
    value.includes('code') ||
    value.includes('test') ||
    value.includes('implement') ||
    value.includes('bug') ||
    value.includes('fix')
  ) {
    return 'code_remote';
  }
  if (value.includes('design') || value.includes('plan') || value.includes('analyze')) {
    return 'reasoning_remote';
  }
  return 'reasoning_remote';
}

function selectProfile(task, options = {}) {
  const available = Array.isArray(options.availableProfiles)
    ? options.availableProfiles
    : PROFILE_ORDER;
  const preferred = profileForIntent(task && task.intent);
  if (available.includes(preferred)) {
    return preferred;
  }
  return available.find((profile) => PROFILE_ORDER.includes(profile)) || available[0] || preferred;
}

function buildFallbacks(profile, options = {}) {
  const available = Array.isArray(options.availableProfiles)
    ? options.availableProfiles
    : PROFILE_ORDER;
  const order = PROFILE_ORDER.filter((item) => item !== profile);
  return [profile, ...order].filter((item) => available.includes(item));
}

module.exports = {
  PROFILE_ORDER,
  profileForIntent,
  selectProfile,
  buildFallbacks
};
