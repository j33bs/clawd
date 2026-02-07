const { estimateTokens } = require('./chain_budget');
const { validatePlan, validateTaskResult } = require('./chain_schema');

function nowIso() {
  return new Date().toISOString();
}

function summarizeText(text, maxChars = 400) {
  if (!text) {
    return '';
  }
  const value = String(text);
  if (value.length <= maxChars) {
    return value;
  }
  return value.slice(0, maxChars - 3) + '...';
}

function intakeStep(state) {
  const text = String(state.request && state.request.text ? state.request.text : '').trim();
  const lower = text.toLowerCase();

  const risk = {
    governance: lower.includes('governance') || lower.includes('compliance'),
    codeChange: lower.includes('refactor') || lower.includes('implement') || lower.includes('code'),
    tests: lower.includes('test') || lower.includes('tests')
  };

  const isTrivial = text.length < 160 && !risk.governance && !risk.codeChange;
  const suggestedMode = isTrivial ? 'fast' : 'chain';

  return {
    requestIntent: summarizeText(text, 240),
    risk,
    suggestedMode,
    createdAt: nowIso()
  };
}

function planFromText(text) {
  const tasks = [];
  let id = 1;

  const lower = String(text || '').toLowerCase();
  if (lower.includes('test')) {
    tasks.push({
      id: `task_${id++}`,
      title: 'Add or update tests',
      intent: 'add tests',
      estTokens: 800,
      risk: 'medium',
      requiresTools: false,
      definitionOfDone: 'Tests updated and described.'
    });
  }

  if (lower.includes('doc') || lower.includes('readme')) {
    tasks.push({
      id: `task_${id++}`,
      title: 'Update documentation',
      intent: 'document',
      estTokens: 500,
      risk: 'low',
      requiresTools: false,
      definitionOfDone: 'Docs updated with new behavior.'
    });
  }

  tasks.push({
    id: `task_${id++}`,
    title: 'Implement requested change',
    intent: 'implement',
    estTokens: 1200,
    risk: 'medium',
    requiresTools: false,
    definitionOfDone: 'Change implemented and summarized.'
  });

  return { tasks: tasks.slice(0, 6) };
}

async function planStep(state, modelAdapter) {
  const text = state.request && state.request.text ? state.request.text : '';

  if (!modelAdapter) {
    return planFromText(text);
  }

  const prompt = `Create a short task plan (2-6 tasks) with id, title, intent, estTokens, risk, requiresTools, definitionOfDone.\nRequest: ${text}`;
  const response = await modelAdapter({
    profile: 'cheap_transform',
    messages: [{ role: 'user', content: prompt }],
    metadata: { intent: 'plan' }
  });

  const parsed = response && response.parsedPlan ? response.parsedPlan : null;
  if (parsed && validatePlan(parsed).ok) {
    return parsed;
  }

  return planFromText(text);
}

function routeStep(plan, router, options = {}) {
  const tasks = Array.isArray(plan.tasks) ? plan.tasks : [];
  return tasks.map((task) => ({
    ...task,
    profile: router.selectProfile(task, options),
    profileFallbacks: router.buildFallbacks(
      router.selectProfile(task, options),
      options
    )
  }));
}

async function executeTaskStep(state, task, modelAdapter) {
  const pinned = state.working && state.working.pinned ? state.working.pinned : {};
  const rollingSummary = state.working && state.working.rollingSummary
    ? state.working.rollingSummary
    : '';

  const prompt = [
    pinned.constitutionNote ? `Constitution: ${pinned.constitutionNote}` : '',
    pinned.userIntent ? `User intent: ${pinned.userIntent}` : '',
    pinned.invariants ? `Invariants: ${pinned.invariants}` : '',
    rollingSummary ? `Rolling summary: ${rollingSummary}` : '',
    `Task: ${task.title}`,
    `Intent: ${task.intent}`,
    `Definition of done: ${task.definitionOfDone || 'Complete task.'}`
  ]
    .filter(Boolean)
    .join('\n');

  if (!modelAdapter) {
    return {
      text: `Stub result for ${task.title}.`,
      notes: [`Executed ${task.intent} task`],
      tokenEst: estimateTokens(prompt)
    };
  }

  const response = await modelAdapter({
    profile: task.profile || 'reasoning_remote',
    messages: [{ role: 'user', content: prompt }],
    metadata: { intent: task.intent }
  });

  const result = {
    text: response && response.text ? response.text : '',
    notes: response && Array.isArray(response.notes) ? response.notes : [],
    tokenEst: estimateTokens(prompt)
  };

  const validation = validateTaskResult(result);
  if (!validation.ok) {
    return {
      text: result.text || '',
      notes: result.notes || [],
      tokenEst: result.tokenEst || 0
    };
  }

  return result;
}

function critiqueNeeded(task, risk) {
  if (risk && (risk.governance || risk.codeChange)) {
    return true;
  }
  if (task && task.risk && String(task.risk).toLowerCase() === 'high') {
    return true;
  }
  return false;
}

async function critiqueStep(state, task, modelAdapter) {
  if (!modelAdapter) {
    return { text: '', notes: [] };
  }

  const prompt = `Critique the task result briefly and list actionable deltas only. Task: ${task.title}`;
  const response = await modelAdapter({
    profile: 'reasoning_remote',
    messages: [{ role: 'user', content: prompt }],
    metadata: { intent: 'critique' }
  });

  return {
    text: response && response.text ? response.text : '',
    notes: response && Array.isArray(response.notes) ? response.notes : []
  };
}

function compressStep(state, taskResults) {
  const notes = taskResults.flatMap((task) => task.notes || []);
  const summary = notes.join(' | ');
  const rollingSummary = summarizeText(summary, 600);

  return {
    rollingSummary,
    perTaskNotes: taskResults.reduce((acc, task) => {
      acc[task.id] = (task.notes || []).slice(0, 8);
      return acc;
    }, {})
  };
}

function finalizeStep(state, taskResults) {
  const text = taskResults
    .map((task) => `- ${task.title}: ${summarizeText(task.text, 400)}`)
    .join('\n');

  return {
    finalText: text || 'No output generated.'
  };
}

module.exports = {
  intakeStep,
  planStep,
  routeStep,
  executeTaskStep,
  critiqueNeeded,
  critiqueStep,
  compressStep,
  finalizeStep
};
