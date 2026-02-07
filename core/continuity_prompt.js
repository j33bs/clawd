const MAX_LOCAL_PROMPT_CHARS = 24000;
const MAX_LOCAL_STATE_SUMMARY_CHARS = 6000;
const DEFAULT_TAIL_TURNS = 4;
const TRUNCATION_NOTE =
  'NOTE: Context truncated for continuity mode (budgeted). Use remote model for full context.';

function normalizeText(value) {
  if (typeof value === 'string') {
    return value.trim();
  }
  return '';
}

function estimateMessageChars(message) {
  if (!message || typeof message !== 'object') {
    return 0;
  }
  const role = String(message.role || 'user');
  const content = typeof message.content === 'string' ? message.content : '';
  return role.length + content.length + 4;
}

function estimateMessagesChars(messages) {
  if (!Array.isArray(messages)) {
    return 0;
  }
  return messages.reduce((sum, message) => sum + estimateMessageChars(message), 0);
}

function truncateFromStart(text, maxChars) {
  if (text.length <= maxChars) {
    return { text, truncated: false };
  }
  const sliced = text.slice(text.length - maxChars);
  return { text: sliced, truncated: true };
}

function clampText(text, maxChars) {
  if (text.length <= maxChars) {
    return { text, truncated: false };
  }
  return truncateFromStart(text, maxChars);
}

function applyPinnedBudget(messages, pinnedCount, noteIndex, maxChars) {
  let truncated = false;
  let totalChars = estimateMessagesChars(messages);

  if (totalChars <= maxChars) {
    return { messages, truncated };
  }

  truncated = true;

  while (messages.length > pinnedCount && totalChars > maxChars) {
    messages.splice(pinnedCount, 1);
    totalChars = estimateMessagesChars(messages);
  }

  for (let i = pinnedCount; i < messages.length; i += 1) {
    if (totalChars <= maxChars) {
      break;
    }
    const message = messages[i];
    const content = typeof message.content === 'string' ? message.content : '';
    if (!content) {
      continue;
    }
    const excess = totalChars - maxChars;
    const reduceBy = Math.min(excess, content.length);
    const result = truncateFromStart(content, content.length - reduceBy);
    message.content = result.text;
    totalChars = estimateMessagesChars(messages);
  }

  if (totalChars > maxChars && pinnedCount > 0) {
    for (let i = 0; i < pinnedCount; i += 1) {
      if (totalChars <= maxChars) {
        break;
      }
      if (i === noteIndex) {
        continue;
      }
      const message = messages[i];
      const content = typeof message.content === 'string' ? message.content : '';
      if (!content) {
        continue;
      }
      const excess = totalChars - maxChars;
      const reduceBy = Math.min(excess, content.length);
      const result = truncateFromStart(content, content.length - reduceBy);
      message.content = result.text;
      totalChars = estimateMessagesChars(messages);
    }
  }

  return { messages, truncated };
}

function buildContinuityMessages({
  system,
  instruction,
  history,
  stateSummary,
  tailTurnsMax,
  budgets
} = {}) {
  const maxPromptChars =
    Number(budgets && budgets.maxPromptChars) || MAX_LOCAL_PROMPT_CHARS;
  const maxStateSummaryChars =
    Number(budgets && budgets.maxStateSummaryChars) || MAX_LOCAL_STATE_SUMMARY_CHARS;
  const maxTailTurns = Number(tailTurnsMax || DEFAULT_TAIL_TURNS);

  const systemText = normalizeText(system);
  const instructionText = normalizeText(instruction);
  const summaryText = normalizeText(stateSummary);

  const pinnedMessages = [];
  if (systemText) {
    pinnedMessages.push({ role: 'system', content: systemText });
  }
  if (instructionText) {
    pinnedMessages.push({ role: 'user', content: instructionText });
  }

  let summaryMessage = null;
  let summaryTrimmed = false;
  if (summaryText) {
    const trimmedSummary = clampText(summaryText, maxStateSummaryChars);
    summaryTrimmed = trimmedSummary.truncated;
    summaryMessage = { role: 'system', content: `State summary:\n${trimmedSummary.text}` };
  }

  const historyList = Array.isArray(history)
    ? history
        .filter((message) => message && typeof message.content === 'string')
        .filter((message) => {
          const role = String(message.role || '').toLowerCase();
          return role === 'user' || role === 'assistant';
        })
    : [];

  const tailMessages = historyList.slice(Math.max(historyList.length - maxTailTurns, 0));

  function assembleMessages(includeNote) {
    const messages = [...pinnedMessages];
    if (includeNote) {
      messages.push({ role: 'system', content: TRUNCATION_NOTE });
    }
    if (summaryMessage) {
      messages.push({ ...summaryMessage });
    }
    tailMessages.forEach((message) => {
      messages.push({
        role: String(message.role || 'user'),
        content: String(message.content || '')
      });
    });
    return messages;
  }

  let messages = assembleMessages(false);
  let budgetResult = applyPinnedBudget(messages, pinnedMessages.length, -1, maxPromptChars);

  if (summaryTrimmed || budgetResult.truncated) {
    const pinnedCount = pinnedMessages.length + 1;
    const noteIndex = pinnedCount - 1;
    messages = assembleMessages(true);
    budgetResult = applyPinnedBudget(messages, pinnedCount, noteIndex, maxPromptChars);
  }

  return budgetResult.messages;
}

function enforceBudget(textOrMessages, maxChars) {
  if (typeof textOrMessages === 'string') {
    const result = clampText(textOrMessages, maxChars);
    return {
      ok: !result.truncated,
      truncated: result.truncated,
      value: result.text,
      droppedInfoNote: result.truncated ? TRUNCATION_NOTE : null
    };
  }

  if (!Array.isArray(textOrMessages)) {
    return {
      ok: true,
      truncated: false,
      value: textOrMessages,
      droppedInfoNote: null
    };
  }

  const messages = textOrMessages.map((message) => ({ ...message }));
  const noteIndex = messages.findIndex(
    (message) => message && message.content === TRUNCATION_NOTE
  );
  const pinnedCount = noteIndex >= 0 ? noteIndex + 1 : 0;
  const budgeted = applyPinnedBudget(messages, pinnedCount, noteIndex, maxChars);

  return {
    ok: !budgeted.truncated,
    truncated: budgeted.truncated,
    value: budgeted.messages,
    droppedInfoNote: budgeted.truncated ? TRUNCATION_NOTE : null
  };
}

module.exports = {
  MAX_LOCAL_PROMPT_CHARS,
  MAX_LOCAL_STATE_SUMMARY_CHARS,
  TRUNCATION_NOTE,
  buildContinuityMessages,
  enforceBudget,
  estimateMessagesChars
};
