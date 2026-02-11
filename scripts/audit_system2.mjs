#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);

const { loadConfig } = require('../sys/config');
const { probeStartupInvariants } = require('../core/system2/startup_invariants');
const { evaluateRoutingDecision } = require('../core/system2/routing_policy_contract');
const { createSignedEnvelope, verifyEnvelope } = require('../core/system2/federated_envelope');
const { System2ToolPlane } = require('../core/system2/tool_plane');
const { System2EventLog } = require('../core/system2/event_log');
const { FederatedRpcV0 } = require('../core/system2/federated_rpc_v0');

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function writeJson(filePath, payload) {
  ensureDir(path.dirname(filePath));
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
}

async function main() {
  const checks = [];
  const projectRoot = process.cwd();

  function addCheck(name, ok, details = {}) {
    checks.push({
      name,
      ok: Boolean(ok),
      ...details
    });
  }

  try {
    const config = loadConfig();
    addCheck('config_load', true, {
      configPath: config.__meta && config.__meta.configPath
    });

    const invariants = probeStartupInvariants({
      config,
      workspaceRoot: projectRoot
    });
    addCheck('startup_invariants', invariants.ok, {
      failed: invariants.checks.filter((check) => !check.ok).map((check) => check.name)
    });
  } catch (error) {
    addCheck('config_and_invariants', false, {
      error: error && error.message ? error.message : String(error)
    });
  }

  try {
    const decision = evaluateRoutingDecision({
      request_type: 'coding',
      privacy_level: 'external_ok',
      urgency: 'interactive',
      provenance: 'first_party',
      tool_needs: ['read_file'],
      budget: { remaining: 4000, cap: 10000 },
      system_health: {
        system1: { state: 'up' },
        system2: { mode: 'normal' }
      }
    });
    const ok = Boolean(decision.selected_model_route) && Boolean(decision.degrade_flags);
    addCheck('routing_policy_contract', ok);
  } catch (error) {
    addCheck('routing_policy_contract', false, {
      error: error && error.message ? error.message : String(error)
    });
  }

  try {
    const envelope = createSignedEnvelope(
      { hello: 'world' },
      { route: 'LOCAL_QWEN' },
      { remaining: 1000 },
      [{ id: 'artifact-1' }],
      {
        signingKey: process.env.SYSTEM2_ENVELOPE_HMAC_KEY || 'system2-audit-smoke-key'
      }
    );
    const verified = verifyEnvelope(envelope, {
      signingKey: process.env.SYSTEM2_ENVELOPE_HMAC_KEY || 'system2-audit-smoke-key'
    });
    addCheck('federated_envelope_signature', verified.ok);
  } catch (error) {
    addCheck('federated_envelope_signature', false, {
      error: error && error.message ? error.message : String(error)
    });
  }

  try {
    const rpc = new FederatedRpcV0({
      signingKey: process.env.SYSTEM2_ENVELOPE_HMAC_KEY || 'system2-audit-smoke-key',
      callSystem1Fn: async () => ({ ok: true, result: { smoke: true } })
    });
    const submitted = await rpc.submitJob({
      target: {
        module: 'core_infra.channel_scoring',
        fn: 'validate_scores',
        args: [{ alpha: 1 }]
      }
    });
    const polled = rpc.pollJob(submitted.jobId);
    addCheck('federated_rpc_submit_poll', Boolean(polled.found));
  } catch (error) {
    addCheck('federated_rpc_submit_poll', false, {
      error: error && error.message ? error.message : String(error)
    });
  }

  try {
    const toolPlane = new System2ToolPlane({
      workspaceRoot: projectRoot
    });
    const toolCall = toolPlane.executeToolCall({
      tool: 'list_dir',
      args: { path: '.' },
      policy: {
        mode: 'allow_readonly',
        allowed_tools: ['list_dir', 'read_file']
      }
    });
    addCheck('tool_plane_readonly', toolCall.ok);
  } catch (error) {
    addCheck('tool_plane_readonly', false, {
      error: error && error.message ? error.message : String(error)
    });
  }

  try {
    const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'system2-audit-eventlog-'));
    const eventLog = new System2EventLog({ workspaceRoot: tmpRoot });
    eventLog.appendEvent({ event_type: 'routing_decision', route: 'LOCAL_QWEN' });
    const batch = eventLog.readEventsSince({ line: 0 });
    const advanced = eventLog.advanceCursor(batch.nextCursor);
    addCheck('event_log_cursor', batch.events.length === 1 && advanced.line === 1);
  } catch (error) {
    addCheck('event_log_cursor', false, {
      error: error && error.message ? error.message : String(error)
    });
  }

  const passed = checks.filter((check) => check.ok).length;
  const completionRate = checks.length > 0 ? passed / checks.length : 0;
  const gateResult = passed === checks.length ? 'pass' : 'fail';

  const evidence = {
    gate_result: gateResult,
    completion_rate: completionRate,
    traces: checks.length,
    smoke_log_truncated: false,
    generated_at: new Date().toISOString(),
    checks
  };

  const primaryEvidencePath = path.join(projectRoot, 'reports', 'system2', 'system2_audit_evidence.json');
  const ciEvidencePath = path.join(projectRoot, 'reports', 'ci', 'system2', 'system2_audit_evidence.json');
  writeJson(primaryEvidencePath, evidence);
  writeJson(ciEvidencePath, evidence);

  const logPath = path.join(projectRoot, 'reports', 'system2', 'system2_audit_smoke.log');
  fs.writeFileSync(
    logPath,
    checks.map((check) => `${check.ok ? 'PASS' : 'FAIL'} ${check.name}`).join('\n') + '\n',
    'utf8'
  );

  console.log(JSON.stringify(evidence, null, 2));
  if (gateResult !== 'pass') {
    process.exit(1);
  }
}

main().catch((error) => {
  console.error(error && error.message ? error.message : String(error));
  process.exit(1);
});
