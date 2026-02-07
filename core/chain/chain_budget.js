const DEFAULT_TOKEN_CEILING = Number(process.env.CHAIN_TOKEN_CEILING || 6000);
const MIN_ROLLING_SUMMARY_CHARS = 240;
const ESTIMATOR_SAFETY = 1.1;

function estimateTokens(text) {
  if (!text) {
    return 0;
  }
  const chars = String(text).length;
  return Math.ceil((chars / 4) * ESTIMATOR_SAFETY);
}

function estimateStateTokens(state) {
  try {
    return estimateTokens(JSON.stringify(state));
  } catch (error) {
    return estimateTokens(String(state || ''));
  }
}

function truncateTail(text, maxChars) {
  if (typeof text !== 'string') {
    return '';
  }
  if (text.length <= maxChars) {
    return text;
  }
  return text.slice(text.length - maxChars);
}

function ensurePinned(pinned) {
  const safePinned = pinned && typeof pinned === 'object' ? { ...pinned } : {};
  const truncationNote = safePinned.truncationNote ||
    'NOTE: Chain budget enforced; context pruned for continuity.';
  return {
    constitutionNote: safePinned.constitutionNote || '',
    truncationNote,
    userIntent: safePinned.userIntent || '',
    invariants: safePinned.invariants || ''
  };
}

function enforceBudget(state, ceilingTokens = DEFAULT_TOKEN_CEILING) {
  const working = state && typeof state === 'object' ? { ...state } : {};
  working.working = working.working && typeof working.working === 'object'
    ? { ...working.working }
    : { pinned: {}, rollingSummary: '', scratch: { perTask: {} } };

  working.working.pinned = ensurePinned(working.working.pinned);
  working.working.scratch = working.working.scratch && typeof working.working.scratch === 'object'
    ? { ...working.working.scratch }
    : { perTask: {} };
  working.working.scratch.perTask =
    working.working.scratch.perTask && typeof working.working.scratch.perTask === 'object'
      ? { ...working.working.scratch.perTask }
      : {};

  let currentTokens = estimateStateTokens(working);
  const notes = [];

  if (currentTokens <= ceilingTokens) {
    return { state: working, ok: true, notes };
  }

  if (Object.keys(working.working.scratch.perTask).length > 0) {
    working.working.scratch.perTask = {};
    notes.push('dropped perTask scratch');
  }

  if (Object.keys(working.working.scratch).length > 0) {
    working.working.scratch = { perTask: {} };
    notes.push('cleared scratch');
  }

  currentTokens = estimateStateTokens(working);
  if (currentTokens <= ceilingTokens) {
    return { state: working, ok: true, notes };
  }

  if (working.outputs && Array.isArray(working.outputs.artifacts)) {
    working.outputs = { ...working.outputs, artifacts: [] };
    notes.push('dropped artifacts');
  }

  currentTokens = estimateStateTokens(working);
  if (currentTokens <= ceilingTokens) {
    return { state: working, ok: true, notes };
  }

  const rolling = String(working.working.rollingSummary || '');
  if (rolling.length > MIN_ROLLING_SUMMARY_CHARS) {
    working.working.rollingSummary = truncateTail(rolling, MIN_ROLLING_SUMMARY_CHARS);
    notes.push('compressed rollingSummary');
  }

  currentTokens = estimateStateTokens(working);
  if (currentTokens <= ceilingTokens) {
    return { state: working, ok: true, notes };
  }

  return {
    state: working,
    ok: false,
    notes: notes.concat('ceiling exceeded; unable to recover')
  };
}

module.exports = {
  DEFAULT_TOKEN_CEILING,
  estimateTokens,
  estimateStateTokens,
  enforceBudget
};
