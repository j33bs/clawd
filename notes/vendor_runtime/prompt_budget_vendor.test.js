#!/usr/bin/env node

'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const LOADER_PATH = path.join(process.cwd(), 'dist', 'loader-BAZoAqqR.js');
const SOURCE = fs.readFileSync(LOADER_PATH, 'utf8');

function runTest(name, fn) {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    console.error(`  ${error.message}`);
    throw error;
  }
}

function extractFunctionSource(name) {
  const marker = `function ${name}(`;
  const start = SOURCE.indexOf(marker);
  assert.ok(start >= 0, `missing function ${name}`);

  const bodyStart = SOURCE.indexOf('{', start);
  assert.ok(bodyStart >= 0, `missing function body for ${name}`);

  let depth = 0;
  for (let i = bodyStart; i < SOURCE.length; i += 1) {
    const ch = SOURCE[i];
    if (ch === '{') depth += 1;
    if (ch === '}') {
      depth -= 1;
      if (depth === 0) {
        return SOURCE.slice(start, i + 1);
      }
    }
  }

  throw new Error(`could not parse function ${name}`);
}

function loadFunctions(names) {
  const sandbox = { module: { exports: {} }, exports: {}, require, console };
  const snippets = names.map((name) => extractFunctionSource(name)).join('\n\n');
  const exportBlock = `\nmodule.exports = { ${names.join(', ')} };\n`;
  const script = new vm.Script(`${snippets}\n${exportBlock}`, { filename: 'extracted-loader-functions.js' });
  script.runInNewContext(sandbox);
  return sandbox.module.exports;
}

runTest('system prompt cap uses truncation marker and cap', () => {
  const { capText } = loadFunctions(['capText']);
  const capped = capText('x'.repeat(13000), 12000, 'SYSTEM');
  assert.ok(capped.length <= 12000);
  assert.ok(capped.startsWith('[TRUNCATED_SYSTEM_HEAD:'), 'expected truncation marker');
});

runTest('history windowing keeps tail within cap', () => {
  const { windowHistoryByChars, measureHistoryChars } = loadFunctions([
    'measureContentChars',
    'measureHistoryChars',
    'windowHistoryByChars'
  ]);
  const history = [
    { role: 'user', content: 'A'.repeat(2000) },
    { role: 'assistant', content: 'B'.repeat(2000) },
    { role: 'user', content: 'C'.repeat(2000) },
    { role: 'assistant', content: 'D'.repeat(2000) },
    { role: 'user', content: 'E'.repeat(2000) }
  ];

  const windowed = windowHistoryByChars(history, 8000);
  const chars = measureHistoryChars(windowed);
  assert.ok(chars <= 8000, `history chars exceeded cap: ${chars}`);
  assert.strictEqual(windowed[windowed.length - 1].content, history[history.length - 1].content);
});

runTest('total budget state sums system + prompt + history', () => {
  const { resolveInputBudgetState } = loadFunctions([
    'measureContentChars',
    'measureHistoryChars',
    'resolveInputBudgetState'
  ]);

  const state = resolveInputBudgetState({
    systemPromptText: 'S'.repeat(1000),
    promptText: 'U'.repeat(500),
    historyMessages: [{ role: 'assistant', content: 'H'.repeat(2000) }]
  });

  assert.strictEqual(state.historyChars, 2000);
  assert.strictEqual(state.totalChars, 3500);
});

runTest('drop order is history first then system tightening in strict pass', () => {
  const strictBlockStart = SOURCE.indexOf('if (approxBudgetChars && budgetState.totalChars > approxBudgetChars)');
  assert.ok(strictBlockStart >= 0, 'strict pass block missing');

  const strictBlock = SOURCE.slice(strictBlockStart, strictBlockStart + 1200);
  const idxHistory = strictBlock.indexOf('const strictHistory = windowHistoryByChars');
  const idxSystem = strictBlock.indexOf('systemPromptText = capText(systemPromptTextBaseline, STRICT_MAX_SYSTEM_PROMPT_CHARS, "SYSTEM")');

  assert.ok(idxHistory >= 0, 'strict history window line missing');
  assert.ok(idxSystem >= 0, 'strict system cap line missing');
  assert.ok(idxHistory < idxSystem, 'expected strict history windowing before strict system cap');
});

runTest('strict second pass and controlled block path exist', () => {
  assert.ok(SOURCE.includes('const STRICT_MAX_SYSTEM_PROMPT_CHARS = 8000;'));
  assert.ok(SOURCE.includes('const STRICT_MAX_HISTORY_CHARS = 4000;'));
  assert.ok(SOURCE.includes('Context trimmed to safe limits. Please send \'continue\' to proceed.'));
});

runTest('audit uses final included-size metrics for embedded_attempt', () => {
  const embeddedAttemptStart = SOURCE.indexOf('phase: "embedded_attempt"');
  assert.ok(embeddedAttemptStart >= 0, 'embedded_attempt audit missing');
  const block = SOURCE.slice(embeddedAttemptStart - 350, embeddedAttemptStart + 700);

  assert.ok(block.includes('approxChars: totalChars'));
  assert.ok(block.includes('userPrompt: promptLen'));
  assert.ok(block.includes('systemPrompt: systemPromptChars'));
  assert.ok(block.includes('history: historyChars'));
});
