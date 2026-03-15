import test from 'node:test';
import assert from 'node:assert/strict';

import {
  QUEUE_FAILURE_TEXT,
  applySourceUiTaskDirectiveToText,
  downgradeUnverifiedQueueClaim,
  extractSourceUiTaskDirective,
  formatSourceUiReceipt
} from '../src/source_ui_queue.mjs';

test('extractSourceUiTaskDirective parses directive payload and strips hidden tag', () => {
  const parsed = extractSourceUiTaskDirective(
    'Queued in Source UI.\n<source-ui-task>{"title":"Constitutional Gradients Proto","description":"proto","priority":"high"}</source-ui-task>'
  );

  assert.equal(parsed.error, null);
  assert.equal(parsed.visibleText, 'Queued in Source UI.');
  assert.equal(parsed.task.title, 'Constitutional Gradients Proto');
  assert.equal(parsed.task.description, 'proto');
  assert.equal(parsed.task.priority, 'high');
  assert.equal(parsed.task.project, 'source-ui');
  assert.equal(parsed.task.status, 'backlog');
});

test('applySourceUiTaskDirectiveToText queues task and appends verified receipt', async () => {
  const result = await applySourceUiTaskDirectiveToText({
    text: 'Queued in Source UI.\n<source-ui-task>{"title":"Constitutional Gradients Proto","description":"proto","priority":"high"}</source-ui-task>',
    fetchImpl: async () => ({
      ok: true,
      status: 200,
      async text() {
        return JSON.stringify({
          id: 1001,
          title: 'Constitutional Gradients Proto',
          status: 'backlog'
        });
      }
    }),
    tasksUrl: 'http://example.test/api/tasks'
  });

  assert.equal(result.queued, true);
  assert.equal(result.receipt.id, 1001);
  assert.match(result.text, /Queued in Source UI\./);
  assert.match(result.text, /Source UI receipt: #1001 Constitutional Gradients Proto \(backlog\)/);
});

test('applySourceUiTaskDirectiveToText falls back safely when queueing fails', async () => {
  const result = await applySourceUiTaskDirectiveToText({
    text: 'Queued in Source UI.\n<source-ui-task>{"title":"Constitutional Gradients Proto"}</source-ui-task>',
    fetchImpl: async () => ({
      ok: false,
      status: 500,
      statusText: 'boom',
      async text() {
        return JSON.stringify({ error: 'backend_down' });
      }
    })
  });

  assert.equal(result.queued, false);
  assert.equal(result.text, QUEUE_FAILURE_TEXT);
  assert.match(result.error.message, /Source UI queue failed/);
});

test('downgradeUnverifiedQueueClaim removes unsupported success wording without a receipt', () => {
  assert.equal(downgradeUnverifiedQueueClaim('queued: "constitutional gradients proto" → Source UI backlog.\nvisible. flowing.'), QUEUE_FAILURE_TEXT);
  assert.equal(
    downgradeUnverifiedQueueClaim(`Queued in Source UI.\n\n${formatSourceUiReceipt({ id: 42, title: 'Task', status: 'backlog' })}`),
    `Queued in Source UI.\n\n${formatSourceUiReceipt({ id: 42, title: 'Task', status: 'backlog' })}`
  );
});
