const { callModel } = require('../model_call');
const { BACKENDS, TASK_CLASSES } = require('../model_constants');
const { estimateTokens, enforceBudget } = require('./chain_budget');
const { appendTrace, DEFAULT_TRACE_PATH } = require('./chain_trace');
const router = require('./chain_router');
const steps = require('./chain_steps');

const DEFAULT_STEP_CEILING = Number(process.env.CHAIN_STEP_TOKEN_CEILING || 2000);

function nowMs() {
  return Date.now();
}

function summarize(text, maxChars = 280) {
  if (!text) {
    return '';
  }
  const value = String(text);
  if (value.length <= maxChars) {
    return value;
  }
  return value.slice(0, maxChars - 3) + '...';
}

function messagesToText(messages) {
  if (!Array.isArray(messages)) {
    return '';
  }
  return messages.map((message) => message.content || '').join('\n');
}

function createAdapter(options = {}) {
  return async ({ profile, messages, metadata }) => {
    const useLocal = profile === 'cheap_transform' && String(process.env.OPENCLAW_LOCAL_FALLBACK || '') === '1';
    const preferredBackend = profile === 'cheap_transform'
      ? null
      : BACKENDS.ANTHROPIC_CLAUDE_API;

    const result = await callModel({
      messages,
      taskClass: profile === 'cheap_transform' ? TASK_CLASSES.BASIC : TASK_CLASSES.NON_BASIC,
      requiresClaude: profile !== 'cheap_transform',
      allowNetwork: useLocal ? false : true,
      preferredBackend,
      metadata
    });

    return {
      text: result && result.response ? result.response.text : '',
      usage: result && result.usage ? result.usage : null,
      backend: result && result.backend ? result.backend : null,
      preferredBackend
    };
  };
}

async function traceStep(traceOptions, entry) {
  await appendTrace(entry, traceOptions);
}

async function runChain(requestText, options = {}) {
  const runId = options.runId || `chain_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  const traceOptions = {
    tracePath: options.tracePath || DEFAULT_TRACE_PATH,
    maxEntries: options.maxTraceEntries
  };

  const adapter = options.modelAdapter || createAdapter(options);
  const tokenCeiling = options.tokenCeiling || undefined;
  const stepCeiling = options.stepCeiling || DEFAULT_STEP_CEILING;

  const state = {
    request: { text: requestText, createdAt: new Date().toISOString() },
    constraints: {
      mode: 'cbp_exec',
      tokenCeiling: tokenCeiling || Number(process.env.CHAIN_TOKEN_CEILING || 6000),
      latencyCeilingMs: Number(process.env.CHAIN_LATENCY_CEILING_MS || 30000)
    },
    plan: { tasks: [] },
    working: {
      pinned: {
        constitutionNote: 'CBP-governed execution with minimal drift.',
        truncationNote: 'NOTE: Chain budget enforced; context pruned for continuity.',
        userIntent: requestText,
        invariants: 'No secrets, no unrelated changes.'
      },
      rollingSummary: '',
      scratch: { perTask: {} }
    },
    outputs: { finalText: '', artifacts: [] },
    trace: { runId, stepIndex: 0 }
  };

  function bumpStep() {
    state.trace.stepIndex += 1;
    return state.trace.stepIndex;
  }

  function enforce(label) {
    const budgeted = enforceBudget(state, tokenCeiling || state.constraints.tokenCeiling);
    if (!budgeted.ok) {
      const error = new Error(`Chain budget exceeded at ${label}`);
      error.code = 'CHAIN_BUDGET_EXCEEDED';
      throw error;
    }
    return budgeted.state;
  }

  const intakeStart = nowMs();
  const intake = steps.intakeStep(state);
  state.request.intent = intake.requestIntent;
  state.request.risk = intake.risk;
  state.request.suggestedMode = intake.suggestedMode;
  state.request.normalizedAt = intake.createdAt;
  bumpStep();
  await traceStep(traceOptions, {
    runId,
    step: 'INTAKE',
    modelProfile: null,
    tokenEstIn: estimateTokens(requestText),
    tokenEstOut: estimateTokens(JSON.stringify(intake)),
    durationMs: nowMs() - intakeStart,
    outcome: 'ok',
    summary: summarize(`mode=${intake.suggestedMode} risk=${JSON.stringify(intake.risk)}`)
  });

  enforce('intake');

  const fastPath = intake.suggestedMode === 'fast' && !options.forceChain;

  if (fastPath) {
    const task = {
      id: 'task_fast',
      title: 'Fast response',
      intent: 'summarize',
      estTokens: stepCeiling,
      risk: 'low',
      requiresTools: false,
      definitionOfDone: 'Provide concise response.'
    };
    task.profile = router.selectProfile(task, options);
    task.profileFallbacks = router.buildFallbacks(task.profile, options);
    state.plan.tasks = [task];
  } else {
    const planStart = nowMs();
    const plan = await steps.planStep(state, adapter);
    state.plan = plan;
    bumpStep();
    await traceStep(traceOptions, {
      runId,
      step: 'PLAN',
      modelProfile: 'cheap_transform',
      tokenEstIn: estimateTokens(requestText),
      tokenEstOut: estimateTokens(JSON.stringify(plan)),
      durationMs: nowMs() - planStart,
      outcome: 'ok',
      summary: summarize(`tasks=${plan.tasks.length}`)
    });

    enforce('plan');

    const routeStart = nowMs();
    const routed = steps.routeStep(plan, router, options);
    state.plan.tasks = routed;
    bumpStep();
    await traceStep(traceOptions, {
      runId,
      step: 'ROUTE',
      modelProfile: null,
      tokenEstIn: estimateTokens(JSON.stringify(plan)),
      tokenEstOut: estimateTokens(JSON.stringify(routed)),
      durationMs: nowMs() - routeStart,
      outcome: 'ok',
      summary: summarize(`routed=${routed.length}`)
    });

    enforce('route');
  }

  const taskResults = [];

  for (const task of state.plan.tasks) {
    const executeStart = nowMs();
    const exec = await steps.executeTaskStep(state, task, adapter);
    taskResults.push({
      id: task.id,
      title: task.title,
      intent: task.intent,
      text: exec.text,
      notes: (exec.notes || []).slice(0, 10)
    });
    bumpStep();
    const fallbackUsed = exec.backend === BACKENDS.OATH_CLAUDE ? 'OATH_CLAUDE' : null;
    await traceStep(traceOptions, {
      runId,
      step: 'EXECUTE',
      modelProfile: task.profile || null,
      tokenEstIn: exec.promptTokens || estimateTokens(exec.text),
      tokenEstOut: estimateTokens(exec.text),
      durationMs: nowMs() - executeStart,
      outcome: 'ok',
      summary: summarize(`task=${task.id} intent=${task.intent}`),
      fallback_used: fallbackUsed
    });

    enforce('execute');

    if (steps.critiqueNeeded(task, state.request.risk)) {
      const critiqueStart = nowMs();
      const critique = await steps.critiqueStep(state, task, adapter);
      bumpStep();
      const critiqueFallback = critique.backend === BACKENDS.OATH_CLAUDE ? 'OATH_CLAUDE' : null;
      await traceStep(traceOptions, {
        runId,
        step: 'CRITIQUE',
        modelProfile: 'reasoning_remote',
        tokenEstIn: critique.promptTokens || estimateTokens(task.title),
        tokenEstOut: estimateTokens(critique.text),
        durationMs: nowMs() - critiqueStart,
        outcome: 'ok',
        summary: summarize(`task=${task.id} critique`),
        fallback_used: critiqueFallback
      });

      if (critique.text) {
        taskResults[taskResults.length - 1].notes =
          taskResults[taskResults.length - 1].notes.concat(critique.notes || []).slice(0, 10);
      }

      enforce('critique');
    }
  }

  const compressStart = nowMs();
  const compressed = steps.compressStep(state, taskResults);
  state.working.rollingSummary = compressed.rollingSummary;
  state.working.scratch.perTask = compressed.perTaskNotes;
  bumpStep();
  await traceStep(traceOptions, {
    runId,
    step: 'COMPRESS',
    modelProfile: null,
    tokenEstIn: estimateTokens(JSON.stringify(taskResults)),
    tokenEstOut: estimateTokens(compressed.rollingSummary),
    durationMs: nowMs() - compressStart,
    outcome: 'ok',
    summary: summarize('compressed rolling summary')
  });

  enforce('compress');

  const finalizeStart = nowMs();
  const finalized = steps.finalizeStep(state, taskResults);
  state.outputs.finalText = finalized.finalText;
  bumpStep();
  await traceStep(traceOptions, {
    runId,
    step: 'FINALIZE',
    modelProfile: null,
    tokenEstIn: estimateTokens(JSON.stringify(taskResults)),
    tokenEstOut: estimateTokens(finalized.finalText),
    durationMs: nowMs() - finalizeStart,
    outcome: 'ok',
    summary: summarize('final response')
  });

  return state;
}

module.exports = {
  runChain
};
