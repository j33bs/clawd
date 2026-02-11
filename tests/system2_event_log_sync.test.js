'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { System2EventLog } = require('../core/system2/event_log');

async function run(name, fn) {
  try {
    await fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    console.error(error.message);
    process.exit(1);
  }
}

async function main() {
  await run('append/read events and monotonic cursor', async () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'system2-event-log-'));
    const log = new System2EventLog({
      workspaceRoot: tmpDir
    });

    log.appendEvent({ event_type: 'routing_decision', route: 'LOCAL_QWEN' });
    log.appendEvent({ event_type: 'model_call', backend: 'LOCAL_QWEN' });

    const batch = log.readEventsSince({ line: 0 });
    assert.strictEqual(batch.events.length, 2);
    assert.strictEqual(batch.nextCursor.line, 2);

    const cursor = log.advanceCursor(batch.nextCursor);
    assert.strictEqual(cursor.line, 2);
    const reloaded = log.readCursor();
    assert.strictEqual(reloaded.line, 2);
  });

  await run('sync skeleton advances cursor only on ack', async () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'system2-event-sync-'));
    const log = new System2EventLog({
      workspaceRoot: tmpDir
    });

    log.appendEvent({ event_type: 'routing_decision', route: 'LOCAL_QWEN' });
    log.appendEvent({ event_type: 'tool_call', tool: 'read_file' });

    let pushedCount = 0;
    const synced = await log.syncWithRemote({
      pushFn: async (events) => {
        pushedCount = events.length;
        return { ok: true };
      }
    });

    assert.strictEqual(pushedCount, 2);
    assert.strictEqual(synced.pushed, 2);
    assert.strictEqual(log.readCursor().line, 2);

    const blocked = await log.syncWithRemote({
      pushFn: async () => ({ ok: false })
    });
    assert.strictEqual(blocked.pushed, 0);
    assert.strictEqual(log.readCursor().line, 2);
  });
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
