const assert = require('assert');

const TelegramCircuitBreaker = require('../core/telegram_circuit_breaker');

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

async function testBreakerOpensAndCloses() {
  let now = 0;
  const logs = [];
  const breaker = new TelegramCircuitBreaker({
    clock: () => now,
    logger: {
      info: (message) => logs.push(`info:${message}`),
      warn: (message) => logs.push(`warn:${message}`)
    },
    chatActionThreshold: 3,
    chatActionCooldownMs: 60 * 1000,
    failureWindowMs: 2 * 60 * 1000
  });

  breaker.recordFailure('sendChatAction');
  breaker.recordFailure('sendChatAction');
  breaker.recordFailure('sendChatAction');

  assert.strictEqual(breaker.isOpen('sendChatAction'), true, 'breaker should open after threshold');

  now += 60 * 1000 + 1;
  assert.strictEqual(breaker.isOpen('sendChatAction'), false, 'breaker should close after cooldown');

  const hasOpenLog = logs.some((entry) => entry.includes('breaker opened'));
  const hasCloseLog = logs.some((entry) => entry.includes('breaker closed'));
  assert.strictEqual(hasOpenLog, true, 'expected open log');
  assert.strictEqual(hasCloseLog, true, 'expected close log');
}

async function main() {
  await runTest('telegram circuit breaker opens and closes', testBreakerOpensAndCloses);
}

main().catch(() => {
  process.exit(1);
});
