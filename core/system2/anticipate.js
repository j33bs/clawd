'use strict';

function isEnabled(env = process.env) {
  return String(env.OPENCLAW_ENABLE_ANTICIPATE || '1') !== '0';
}

function normalizeMessages(messages) {
  if (!Array.isArray(messages)) return [];
  return messages
    .map((msg) => {
      if (typeof msg === 'string') return msg;
      if (!msg || typeof msg !== 'object') return '';
      return String(msg.content || msg.text || '');
    })
    .filter(Boolean);
}

function suggestAutomations(messages, opts = {}) {
  const env = opts.env || process.env;
  if (!isEnabled(env)) {
    return { enabled: false, mode: 'suggestion_only', suggestions: [] };
  }

  const text = normalizeMessages(messages).join('\n').toLowerCase();
  const suggestions = [];

  if (/\b(daily|every day)\b.*\b(report|summary|digest)\b/.test(text)) {
    suggestions.push({
      id: 'daily_report',
      title: 'Create a daily report automation',
      reason: 'Recurring daily reporting intent detected.',
      risk: 'low',
      autoEnable: false
    });
  }

  if (/\b(remind|reminder)\b.*\b(meeting|calendar|event)\b/.test(text)) {
    suggestions.push({
      id: 'meeting_reminder',
      title: 'Create a meeting reminder automation',
      reason: 'Recurring reminder intent detected.',
      risk: 'low',
      autoEnable: false
    });
  }

  return {
    enabled: true,
    mode: 'suggestion_only',
    suggestions
  };
}

module.exports = {
  isEnabled,
  suggestAutomations
};
