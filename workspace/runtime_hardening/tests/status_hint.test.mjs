import test from 'node:test';
import assert from 'node:assert/strict';

import { buildUnknownPortHint } from '../src/status_hint.mjs';

test('status hint appears when vLLM is unhealthy and port owner is unknown', () => {
  const hint = buildUnknownPortHint({
    vllmHealthy: false,
    probe: {
      kind: 'unknown',
      pid: 43210,
      cmd: 'python3 -m http.server 8001'
    },
    port: 8001
  });

  assert.equal(typeof hint, 'string');
  assert.match(hint, /^HINT: vLLM blocked/);
  assert.match(hint, /pid=43210/);
  assert.match(hint, /cmd="python3 -m http\.server 8001"/);
});

test('status hint is suppressed for vllm_like holder', () => {
  const hint = buildUnknownPortHint({
    vllmHealthy: false,
    probe: {
      kind: 'vllm_like',
      pid: 222,
      cmd: 'vllm serve ...'
    },
    port: 8001
  });

  assert.equal(hint, null);
});

test('status hint is suppressed when port is free', () => {
  const hint = buildUnknownPortHint({
    vllmHealthy: false,
    probe: {
      kind: 'free',
      held: false
    },
    port: 8001
  });

  assert.equal(hint, null);
});
