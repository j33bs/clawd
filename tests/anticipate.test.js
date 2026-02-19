'use strict';

const assert = require('node:assert');
const { suggestAutomations } = require('../core/system2/anticipate');

function testSuggestionOnlyDefaults() {
  const result = suggestAutomations([
    'Please send me a daily report summary of alerts.',
    'Also remind me for each meeting on my calendar.'
  ]);

  assert.strictEqual(result.enabled, true);
  assert.strictEqual(result.mode, 'suggestion_only');
  assert.ok(result.suggestions.length >= 2);
  assert.ok(result.suggestions.every((s) => s.autoEnable === false));
  console.log('PASS anticipate module emits suggestion-only low-risk automation hints');
}

function testFlagCanDisable() {
  const result = suggestAutomations(
    ['daily report please'],
    { env: { OPENCLAW_ENABLE_ANTICIPATE: '0' } }
  );
  assert.strictEqual(result.enabled, false);
  assert.strictEqual(result.suggestions.length, 0);
  console.log('PASS anticipate feature flag disables suggestions');
}

function main() {
  testSuggestionOnlyDefaults();
  testFlagCanDisable();
}

main();
