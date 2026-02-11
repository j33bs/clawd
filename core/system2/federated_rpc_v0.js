'use strict';

const { callSystem1 } = require('../integration/system1_adapter');
const { createSignedEnvelope, verifyEnvelope } = require('./federated_envelope');

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

class FederatedRpcV0 {
  constructor(options = {}) {
    this.callSystem1Fn = options.callSystem1Fn || callSystem1;
    this.signingKey = options.signingKey || null;
    this.keyEnv = options.keyEnv || 'SYSTEM2_ENVELOPE_HMAC_KEY';
    this.jobs = new Map();
  }

  async submitJob(request = {}) {
    const envelope = createSignedEnvelope(
      request.payload || {},
      request.policy_decision_record || {},
      request.budgets || {},
      request.artifacts_manifest || [],
      {
        signingKey: this.signingKey,
        keyEnv: this.keyEnv,
        requesterIdentity: request.requester_identity || 'system2'
      }
    );

    const verification = verifyEnvelope(envelope, {
      signingKey: this.signingKey,
      keyEnv: this.keyEnv
    });
    if (!verification.ok) {
      throw new Error(`Envelope verification failed: ${verification.errors.join('; ')}`);
    }

    const record = {
      job_id: envelope.job_id,
      envelope,
      request,
      status: 'accepted',
      created_at: envelope.created_at,
      updated_at: envelope.created_at,
      cancelled: false,
      result: null,
      error: null,
      chunks: []
    };

    this.jobs.set(record.job_id, record);
    this._execute(record.job_id).catch(() => {});

    return {
      jobId: record.job_id,
      envelope,
      accepted: true
    };
  }

  async _execute(jobId) {
    const record = this.jobs.get(jobId);
    if (!record) {
      return;
    }
    if (record.cancelled) {
      return;
    }

    record.status = 'running';
    record.updated_at = new Date().toISOString();
    record.chunks.push({
      ts: record.updated_at,
      type: 'job_started'
    });

    const target = record.request.target || {};
    const moduleName = target.module || target.moduleName || 'core_infra.channel_scoring';
    const fnName = target.fn || target.fnName || 'validate_scores';
    const args = Array.isArray(target.args) ? target.args : [{}];

    try {
      const result = await this.callSystem1Fn(moduleName, fnName, args, target.options || {});
      if (record.cancelled) {
        return;
      }
      record.result = result;
      record.status = 'completed';
      record.updated_at = new Date().toISOString();
      record.chunks.push({
        ts: record.updated_at,
        type: 'job_completed',
        result
      });
    } catch (error) {
      if (record.cancelled) {
        return;
      }
      record.error = error && error.message ? error.message : String(error);
      record.status = 'failed';
      record.updated_at = new Date().toISOString();
      record.chunks.push({
        ts: record.updated_at,
        type: 'job_failed',
        error: record.error
      });
    }
  }

  pollJob(jobId) {
    const record = this.jobs.get(jobId);
    if (!record) {
      return {
        found: false,
        job_id: jobId,
        status: 'unknown'
      };
    }
    return {
      found: true,
      job_id: record.job_id,
      status: record.status,
      updated_at: record.updated_at,
      cancelled: record.cancelled,
      result: record.result,
      error: record.error
    };
  }

  async *streamJob(jobId, options = {}) {
    const intervalMs = Number(options.intervalMs ?? 100);
    const timeoutMs = Number(options.timeoutMs ?? 15000);
    const startedAt = Date.now();
    let index = 0;

    while (Date.now() - startedAt <= timeoutMs) {
      const record = this.jobs.get(jobId);
      if (!record) {
        yield {
          job_id: jobId,
          status: 'unknown',
          done: true
        };
        return;
      }

      while (index < record.chunks.length) {
        yield {
          job_id: jobId,
          status: record.status,
          chunk: record.chunks[index],
          done: false
        };
        index += 1;
      }

      if (['completed', 'failed', 'cancelled'].includes(record.status)) {
        yield {
          job_id: jobId,
          status: record.status,
          done: true
        };
        return;
      }

      await sleep(intervalMs);
    }

    yield {
      job_id: jobId,
      status: this.pollJob(jobId).status,
      done: true,
      timeout: true
    };
  }

  cancelJob(jobId) {
    const record = this.jobs.get(jobId);
    if (!record) {
      return {
        cancelled: false,
        reason: 'not_found'
      };
    }
    if (['completed', 'failed', 'cancelled'].includes(record.status)) {
      return {
        cancelled: false,
        reason: 'terminal'
      };
    }

    record.cancelled = true;
    record.status = 'cancelled';
    record.updated_at = new Date().toISOString();
    record.chunks.push({
      ts: record.updated_at,
      type: 'job_cancelled'
    });

    return {
      cancelled: true,
      job_id: jobId
    };
  }
}

module.exports = {
  FederatedRpcV0
};
