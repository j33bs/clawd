'use strict';

const assert = require('node:assert');

const { FederatedRpcV0 } = require('../core/system2/federated_rpc_v0');
const { verifyEnvelope } = require('../core/system2/federated_envelope');

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

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
  await run('submit and poll complete federated job', async () => {
    const rpc = new FederatedRpcV0({
      signingKey: 'test-key',
      callSystem1Fn: async () => ({ ok: true, result: { score: 1 } })
    });

    const submitted = await rpc.submitJob({
      target: {
        module: 'core_infra.channel_scoring',
        fn: 'validate_scores',
        args: [{ alpha: 1 }]
      }
    });

    const verify = verifyEnvelope(submitted.envelope, { signingKey: 'test-key' });
    assert.strictEqual(verify.ok, true);

    await sleep(30);
    const polled = rpc.pollJob(submitted.jobId);
    assert.strictEqual(polled.found, true);
    assert.strictEqual(polled.status, 'completed');
    assert.strictEqual(polled.result.ok, true);
  });

  await run('cancel marks running job as cancelled', async () => {
    const rpc = new FederatedRpcV0({
      signingKey: 'test-key',
      callSystem1Fn: async () => {
        await sleep(100);
        return { ok: true };
      }
    });

    const submitted = await rpc.submitJob({
      target: {
        module: 'core_infra.channel_scoring',
        fn: 'validate_scores',
        args: [{ alpha: 1 }]
      }
    });

    const cancel = rpc.cancelJob(submitted.jobId);
    assert.strictEqual(cancel.cancelled, true);

    const polled = rpc.pollJob(submitted.jobId);
    assert.strictEqual(polled.status, 'cancelled');
  });
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
