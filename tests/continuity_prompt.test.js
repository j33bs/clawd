const assert = require('assert');

const {
  MAX_LOCAL_PROMPT_CHARS,
  buildContinuityMessages,
  estimateMessagesChars
} = require('../core/continuity_prompt');

async function runTest(name, fn) {
  try {
    await fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    console.error(`  ${error.message}`);
    throw error;
  }
}

async function testHugeHistoryBudgeted() {
  const largeChunk = 'y'.repeat(4000);
  const history = [];
  for (let i = 0; i < 8; i += 1) {
    history.push({ role: 'user', content: `User ${i} ${largeChunk}` });
    history.push({ role: 'assistant', content: `Assistant ${i} ${largeChunk}` });
  }

  const messages = buildContinuityMessages({
    system: 'System prompt',
    instruction: 'Summarize the latest status',
    history,
    stateSummary: 'state summary',
    tailTurnsMax: 4
  });

  const totalChars = estimateMessagesChars(messages);
  assert.ok(totalChars <= MAX_LOCAL_PROMPT_CHARS, 'budget should be enforced');
  assert.strictEqual(messages[0].role, 'system');
  assert.ok(
    messages.some((message) =>
      String(message.content || '').includes('Context truncated for continuity mode')
    ),
    'expected truncation note'
  );
}

async function testExtremeTruncationNote() {
  const history = [{ role: 'user', content: 'z'.repeat(MAX_LOCAL_PROMPT_CHARS * 2) }];
  const messages = buildContinuityMessages({
    system: 'System prompt',
    instruction: 'Instruction',
    history,
    stateSummary: 'state summary'
  });

  const totalChars = estimateMessagesChars(messages);
  assert.ok(totalChars <= MAX_LOCAL_PROMPT_CHARS, 'budget should be enforced');
  assert.ok(
    messages.some((message) =>
      String(message.content || '').includes('Context truncated for continuity mode')
    ),
    'expected truncation note'
  );
}

async function testSmallUnchanged() {
  const history = [
    { role: 'user', content: 'Hello' },
    { role: 'assistant', content: 'Hi there' }
  ];

  const messages = buildContinuityMessages({
    system: 'System prompt',
    instruction: 'Instruction',
    history,
    stateSummary: 'state summary'
  });

  const totalChars = estimateMessagesChars(messages);
  assert.ok(totalChars < MAX_LOCAL_PROMPT_CHARS, 'small prompt should be under budget');
  const noteFound = messages.some((message) =>
    String(message.content || '').includes('Context truncated for continuity mode')
  );
  assert.strictEqual(noteFound, false, 'did not expect truncation note');
}

async function main() {
  await runTest('continuity prompt budgeted for huge history', testHugeHistoryBudgeted);
  await runTest('continuity prompt adds note when truncated', testExtremeTruncationNote);
  await runTest('continuity prompt unchanged when small', testSmallUnchanged);
}

main().catch(() => {
  process.exit(1);
});
