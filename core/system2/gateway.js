'use strict';

/**
 * System-2 Peer Gateway
 *
 * Central HTTP entrypoint that:
 * - Probes and asserts startup invariants
 * - Accepts requests and applies the Routing Policy Contract
 * - Enforces budget circuit breakers
 * - Manages operational modes (normal, burst, degraded, recovery)
 * - Hosts the MCP tool plane with read-only tools
 * - Exposes Federated RPC endpoints (submit, poll, cancel)
 * - Emits structured observability events
 * - Maintains offline-first event logs with cursor sync
 *
 * This is the implementation of Section 3 + Section 5 + Section 10
 * of the System-2 Design Brief.
 */

const http = require('node:http');
const crypto = require('node:crypto');
const { loadConfig } = require('../../sys/config');
const { probeStartupInvariants } = require('./startup_invariants');
const { evaluateRoutingDecision } = require('./routing_policy_contract');
const { BudgetCircuitBreaker } = require('./budget_circuit_breaker');
const { DegradedModeController, MODES } = require('./degraded_mode_controller');
const { System2ToolPlane } = require('./tool_plane');
const { System2EventLog } = require('./event_log');
const { FederatedRpcV0 } = require('./federated_rpc_v0');

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    const limit = 1024 * 1024; // 1 MB
    req.on('data', (chunk) => {
      size += chunk.length;
      if (size > limit) {
        reject(new Error('Request body too large'));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}

function parseJson(body) {
  try {
    return JSON.parse(body);
  } catch (_) {
    return null;
  }
}

function jsonResponse(res, statusCode, payload) {
  const body = JSON.stringify(payload, null, 2);
  res.writeHead(statusCode, {
    'content-type': 'application/json',
    'content-length': Buffer.byteLength(body)
  });
  res.end(body);
}

class System2Gateway {
  constructor(options = {}) {
    this.workspaceRoot = options.workspaceRoot || process.cwd();
    this.config = options.config || loadConfig();
    this.system2Config = this.config.system2 || {};
    this.port = Number(options.port ?? this.system2Config.gateway_port ?? 4100);
    this.host = options.host || this.system2Config.gateway_host || '127.0.0.1';

    // Run ID for this gateway instance
    this.runId = options.runId || crypto.randomUUID();
    this.startedAt = null;
    this.server = null;

    // Startup invariants result
    this.invariants = null;

    // Core subsystems
    this.eventLog = new System2EventLog({
      workspaceRoot: this.workspaceRoot,
      eventLogPath: this.system2Config.event_log_path,
      cursorPath: this.system2Config.sync_cursor_path
    });

    this.budget = new BudgetCircuitBreaker({
      tokenCap: Number(this.system2Config.token_budget_cap ?? 100000),
      callCap: Number(this.system2Config.call_budget_cap ?? 200),
      onEvent: (event) => this._logEvent(event)
    });

    this.modeController = new DegradedModeController({
      onEvent: (event) => this._logEvent(event)
    });

    this.toolPlane = new System2ToolPlane({
      workspaceRoot: this.workspaceRoot,
      allowlistPath: this.system2Config.tool_allowlist_path
        ? require('node:path').resolve(this.workspaceRoot, this.system2Config.tool_allowlist_path)
        : undefined,
      onEvent: (event) => this._logEvent(event)
    });

    const signingKey =
      options.signingKey ||
      process.env[this.system2Config.envelope_signing_key_env || 'SYSTEM2_ENVELOPE_HMAC_KEY'] ||
      null;

    this.federatedRpc = new FederatedRpcV0({
      signingKey,
      keyEnv: this.system2Config.envelope_signing_key_env || 'SYSTEM2_ENVELOPE_HMAC_KEY',
      callSystem1Fn: options.callSystem1Fn || undefined
    });

    // System-1 health state (updated by health probes or federation)
    this.system1Health = { state: 'up' };
  }

  /**
   * Append a structured event to the offline-first event log.
   */
  _logEvent(event) {
    const enriched = {
      run_id: this.runId,
      gateway: 'system2',
      ...event
    };
    try {
      this.eventLog.appendEvent(enriched);
    } catch (_) {
      // Fail silently to avoid crashing the gateway on log writes
    }
  }

  /**
   * Probe startup invariants and record the result.
   */
  _probeInvariants() {
    this.invariants = probeStartupInvariants({
      config: this.config,
      workspaceRoot: this.workspaceRoot
    });

    this._logEvent({
      event_type: 'startup_invariants',
      ok: this.invariants.ok,
      failed: this.invariants.checks.filter((c) => !c.ok).map((c) => c.name)
    });

    return this.invariants;
  }

  /**
   * Evaluate a routing decision using the Routing Policy Contract.
   */
  _evaluateRoute(request = {}) {
    const budgetAlloc = this.budget.getAllocation();
    const modeState = this.modeController.getState();

    const decision = evaluateRoutingDecision({
      request_type: request.request_type || 'general',
      privacy_level: request.privacy_level || 'external_ok',
      urgency: request.urgency || 'interactive',
      provenance: request.provenance || 'first_party',
      tool_needs: request.tool_needs || [],
      budget: {
        remaining: budgetAlloc.remaining,
        cap: budgetAlloc.cap
      },
      system_health: {
        system1: this.system1Health,
        system2: { mode: modeState.mode }
      }
    });

    // Merge mode controller degrade flags
    const modeFlags = this.modeController.getDegradeFlags();
    if (modeFlags.tools_disabled) {
      decision.degrade_flags.tools_disabled = true;
    }
    if (modeFlags.local_only) {
      decision.degrade_flags.local_only = true;
    }
    if (modeFlags.read_only_memory) {
      decision.degrade_flags.read_only_memory = true;
    }
    if (modeFlags.deny_reason && !decision.degrade_flags.deny_reason) {
      decision.degrade_flags.deny_reason = modeFlags.deny_reason;
    }

    this._logEvent({
      event_type: 'routing_decision',
      selected_model_route: decision.selected_model_route,
      degrade_flags: decision.degrade_flags,
      budget_allocation: decision.budget_allocation,
      mode: modeState.mode
    });

    return decision;
  }

  /**
   * Route handler dispatch.
   */
  async _handleRequest(req, res) {
    const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
    const pathname = url.pathname;
    const method = req.method;

    try {
      // Health / status
      if (pathname === '/health' && method === 'GET') {
        return this._handleHealth(req, res);
      }

      // Routing decision evaluation
      if (pathname === '/v0/route' && method === 'POST') {
        return await this._handleRoute(req, res);
      }

      // Tool plane execution
      if (pathname === '/v0/tool' && method === 'POST') {
        return await this._handleToolCall(req, res);
      }

      // Federated RPC
      if (pathname === '/v0/jobs/submit' && method === 'POST') {
        return await this._handleJobSubmit(req, res);
      }
      if (pathname === '/v0/jobs/poll' && method === 'POST') {
        return await this._handleJobPoll(req, res);
      }
      if (pathname === '/v0/jobs/cancel' && method === 'POST') {
        return await this._handleJobCancel(req, res);
      }

      // Event log read
      if (pathname === '/v0/events' && method === 'GET') {
        return this._handleEventsRead(req, res, url);
      }

      // Mode control (operator UX)
      if (pathname === '/v0/mode' && method === 'GET') {
        return this._handleModeGet(req, res);
      }
      if (pathname === '/v0/mode' && method === 'POST') {
        return await this._handleModeSet(req, res);
      }

      // Budget status / reset
      if (pathname === '/v0/budget' && method === 'GET') {
        return this._handleBudgetGet(req, res);
      }
      if (pathname === '/v0/budget/reset' && method === 'POST') {
        return await this._handleBudgetReset(req, res);
      }

      // System-1 health update (federation callback)
      if (pathname === '/v0/system1/health' && method === 'POST') {
        return await this._handleSystem1HealthUpdate(req, res);
      }

      // 404
      jsonResponse(res, 404, { error: 'not_found', path: pathname });
    } catch (error) {
      this._logEvent({
        event_type: 'error_classified',
        error: error.message || String(error),
        path: pathname,
        method
      });
      jsonResponse(res, 500, {
        error: 'internal_error',
        message: error.message || String(error)
      });
    }
  }

  // --- Route Handlers ---

  _handleHealth(_req, res) {
    const modeState = this.modeController.getState();
    const budgetAlloc = this.budget.getAllocation();
    jsonResponse(res, 200, {
      status: 'ok',
      gateway: 'system2',
      run_id: this.runId,
      started_at: this.startedAt,
      mode: modeState.mode,
      budget: {
        state: budgetAlloc.state,
        remaining: budgetAlloc.remaining,
        cap: budgetAlloc.cap
      },
      invariants_ok: this.invariants ? this.invariants.ok : null,
      system1_health: this.system1Health
    });
  }

  async _handleRoute(req, res) {
    const body = parseJson(await readBody(req));
    if (!body) {
      return jsonResponse(res, 400, { error: 'invalid_json' });
    }

    // Check budget before evaluating
    if (!this.budget.canProceed(body.estimated_tokens || 0)) {
      this._logEvent({
        event_type: 'budget_exhausted',
        reason: 'pre_route_check',
        estimated_tokens: body.estimated_tokens
      });
      return jsonResponse(res, 429, {
        error: 'budget_exhausted',
        budget: this.budget.getAllocation()
      });
    }

    const decision = this._evaluateRoute(body);
    jsonResponse(res, 200, decision);
  }

  async _handleToolCall(req, res) {
    const body = parseJson(await readBody(req));
    if (!body) {
      return jsonResponse(res, 400, { error: 'invalid_json' });
    }

    // Check if tools are disabled by mode controller
    const degradeFlags = this.modeController.getDegradeFlags();
    if (degradeFlags.tools_disabled) {
      return jsonResponse(res, 503, {
        error: 'tools_disabled',
        mode: this.modeController.mode,
        reason: degradeFlags.deny_reason
      });
    }

    const policy = body.policy || {
      mode: 'allow_readonly',
      allowed_tools: ['list_dir', 'read_file']
    };

    const result = this.toolPlane.executeToolCall({
      tool: body.tool,
      args: body.args || {},
      policy
    });

    jsonResponse(res, result.ok ? 200 : 403, result);
  }

  async _handleJobSubmit(req, res) {
    const body = parseJson(await readBody(req));
    if (!body) {
      return jsonResponse(res, 400, { error: 'invalid_json' });
    }

    try {
      const result = await this.federatedRpc.submitJob(body);
      this._logEvent({
        event_type: 'federated_job_submitted',
        job_id: result.jobId,
        accepted: result.accepted
      });
      jsonResponse(res, 202, result);
    } catch (error) {
      this._logEvent({
        event_type: 'error_classified',
        error: error.message || String(error),
        context: 'job_submit'
      });
      jsonResponse(res, 500, {
        error: 'job_submit_failed',
        message: error.message || String(error)
      });
    }
  }

  async _handleJobPoll(req, res) {
    const body = parseJson(await readBody(req));
    if (!body || !body.job_id) {
      return jsonResponse(res, 400, { error: 'missing_job_id' });
    }

    const result = this.federatedRpc.pollJob(body.job_id);
    jsonResponse(res, result.found ? 200 : 404, result);
  }

  async _handleJobCancel(req, res) {
    const body = parseJson(await readBody(req));
    if (!body || !body.job_id) {
      return jsonResponse(res, 400, { error: 'missing_job_id' });
    }

    const result = this.federatedRpc.cancelJob(body.job_id);
    jsonResponse(res, result.cancelled ? 200 : 409, result);
  }

  _handleEventsRead(_req, res, url) {
    const cursorLine = Number(url.searchParams.get('cursor') || 0);
    const batch = this.eventLog.readEventsSince({ line: cursorLine });
    jsonResponse(res, 200, batch);
  }

  _handleModeGet(_req, res) {
    jsonResponse(res, 200, this.modeController.getState());
  }

  async _handleModeSet(req, res) {
    const body = parseJson(await readBody(req));
    if (!body || !body.mode) {
      return jsonResponse(res, 400, { error: 'missing_mode' });
    }

    try {
      const state = this.modeController.transitionTo(body.mode, body.reason || 'operator_override');
      jsonResponse(res, 200, state);
    } catch (error) {
      jsonResponse(res, 400, {
        error: 'invalid_mode',
        message: error.message || String(error)
      });
    }
  }

  _handleBudgetGet(_req, res) {
    jsonResponse(res, 200, this.budget.getAllocation());
  }

  async _handleBudgetReset(req, res) {
    const body = parseJson(await readBody(req));
    const result = this.budget.reset(body || {});
    jsonResponse(res, 200, result);
  }

  async _handleSystem1HealthUpdate(req, res) {
    const body = parseJson(await readBody(req));
    if (!body || !body.state) {
      return jsonResponse(res, 400, { error: 'missing_state' });
    }

    this.system1Health = { state: body.state };

    // Re-evaluate mode based on new health data
    this.modeController.evaluate({
      system1: this.system1Health,
      system2: {
        budget_ok: this.budget.state !== 'open',
        tool_plane_ok: true,
        inference_ok: true
      },
      budget_exhausted: this.budget.state === 'open'
    });

    jsonResponse(res, 200, {
      system1_health: this.system1Health,
      mode: this.modeController.getState()
    });
  }

  /**
   * Start the gateway server.
   */
  async start() {
    // Step 1: Probe and assert startup invariants
    this._probeInvariants();

    // Step 2: Create HTTP server
    this.server = http.createServer((req, res) => {
      this._handleRequest(req, res).catch((error) => {
        try {
          jsonResponse(res, 500, {
            error: 'internal_error',
            message: error.message || String(error)
          });
        } catch (_) {
          res.end();
        }
      });
    });

    // Step 3: Listen
    return new Promise((resolve, reject) => {
      this.server.on('error', reject);
      this.server.listen(this.port, this.host, () => {
        this.startedAt = new Date().toISOString();
        this._logEvent({
          event_type: 'gateway_started',
          port: this.port,
          host: this.host,
          run_id: this.runId,
          invariants_ok: this.invariants ? this.invariants.ok : null
        });
        resolve({
          port: this.port,
          host: this.host,
          runId: this.runId,
          startedAt: this.startedAt,
          invariants: this.invariants
        });
      });
    });
  }

  /**
   * Stop the gateway server.
   */
  async stop() {
    if (!this.server) {
      return;
    }
    return new Promise((resolve) => {
      this.server.close(() => {
        this._logEvent({
          event_type: 'gateway_stopped',
          run_id: this.runId
        });
        this.server = null;
        resolve();
      });
    });
  }
}

module.exports = {
  System2Gateway
};
