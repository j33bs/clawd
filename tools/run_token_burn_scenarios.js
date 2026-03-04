#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const { _test: registryTest } = require('../core/system2/inference/provider_registry');
const { sanitizeToolOutputsForContext } = require('../core/system2/inference/tool_output_sanitizer');
const { hashHex } = require('../core/system2/inference/token_usage_logger');

function parseArgs(argv) {
  const args = {
    before: path.resolve('workspace/logs/token_usage.before.jsonl'),
    after: path.resolve('workspace/logs/token_usage.after.jsonl'),
    runId: `scenario_${new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z')}`
  };

  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--before' && value) {
      args.before = path.resolve(value);
      i += 1;
    } else if (key === '--after' && value) {
      args.after = path.resolve(value);
      i += 1;
    } else if (key === '--run-id' && value) {
      args.runId = value;
      i += 1;
    } else if (key === '-h' || key === '--help') {
      console.log('Usage: node tools/run_token_burn_scenarios.js [--before path] [--after path] [--run-id id]');
      process.exit(0);
    }
  }
  return args;
}

function estimateTokensFromChars(chars) {
  return Math.ceil(Math.max(0, Number(chars) || 0) / 4);
}

function toolPayload(chars, lines) {
  const parts = [];
  for (let i = 0; i < lines; i += 1) {
    parts.push(`line_${String(i + 1).padStart(3, '0')} ${'x'.repeat(Math.max(1, Math.floor(chars / lines) - 14))}`);
  }
  return parts.join('\n');
}

const SCENARIOS = Object.freeze([
  { name: 'simple_ask', reason: 'fast_chat', userChars: 220, toolChars: 0, outTokens: 140 },
  { name: 'code_format', reason: 'code', userChars: 1600, toolChars: 0, outTokens: 220 },
  { name: 'web_search', reason: 'tool_use', userChars: 340, toolChars: 14000, outTokens: 180 },
  { name: 'summarization', reason: 'long_context', userChars: 6800, toolChars: 0, outTokens: 260 },
  { name: 'rag_like', reason: 'long_context', userChars: 1200, toolChars: 18000, outTokens: 280 },
  { name: 'shell_log_analysis', reason: 'tool_use', userChars: 500, toolChars: 22000, outTokens: 210 },
  { name: 'json_api_digest', reason: 'tool_use', userChars: 420, toolChars: 16000, outTokens: 200, jsonTool: true },
  { name: 'doc_rewrite', reason: 'fast_chat', userChars: 4200, toolChars: 0, outTokens: 240 },
  { name: 'debug_trace', reason: 'code', userChars: 1500, toolChars: 20000, outTokens: 250, forceFallback: true },
  { name: 'qa_followup', reason: 'fast_chat', userChars: 380, toolChars: 0, outTokens: 130 }
]);

function buildMessages(scenario) {
  const messages = [
    { role: 'system', content: 'You are a practical coding assistant. Keep responses concise and correct.' },
    { role: 'user', content: `Scenario ${scenario.name}\n${'u'.repeat(scenario.userChars)}` }
  ];
  if (scenario.toolChars > 0) {
    if (scenario.jsonTool) {
      const arr = [];
      const itemChars = Math.max(20, Math.floor(scenario.toolChars / 120));
      for (let i = 0; i < 120; i += 1) {
        arr.push({ title: `result_${i + 1}`, snippet: 's'.repeat(itemChars), score: i + 1 });
      }
      messages.push({ role: 'tool', name: 'web.search', content: JSON.stringify({ items: arr }) });
    } else {
      messages.push({ role: 'tool', name: 'exec', content: toolPayload(scenario.toolChars, 180) });
    }
  }
  return messages;
}

function simulateMode(mode, runId) {
  const rows = [];
  for (let i = 0; i < SCENARIOS.length; i += 1) {
    const scenario = SCENARIOS[i];
    const originalMessages = buildMessages(scenario);
    const toolChars = originalMessages
      .filter((m) => m && m.role === 'tool')
      .map((m) => (typeof m.content === 'string' ? m.content.length : JSON.stringify(m.content).length))
      .reduce((sum, n) => sum + n, 0);

    let effectiveMessages = originalMessages;
    let effectiveToolChars = toolChars;
    if (mode === 'after') {
      const sanitized = sanitizeToolOutputsForContext(originalMessages, {
        env: {
          OPENCLAW_TOOL_OUTPUT_MAX_CHARS: '6000',
          OPENCLAW_RUN_ID: runId
        }
      });
      effectiveMessages = sanitized.messages;
      effectiveToolChars = sanitized.total_tool_output_chars;
    }

    const shape = registryTest.estimateRequestShape(effectiveMessages);
    const tokensIn = estimateTokensFromChars(shape.char_count_total);
    const tokensOut = scenario.outTokens;
    const totalTokens = tokensIn + tokensOut;
    const provider = mode === 'before'
      ? 'xai'
      : (scenario.forceFallback ? 'groq' : 'ollama');
    const model = mode === 'before'
      ? 'xai/grok-4-1-fast'
      : (scenario.forceFallback ? 'groq/llama-3.3-70b-versatile' : 'ollama/qwen2.5-coder:7b');

    rows.push({
      ts_utc: new Date(Date.UTC(2026, 2, 4, 1, i, 0)).toISOString(),
      request_id: `${mode}_${String(i + 1).padStart(2, '0')}_${scenario.name}`,
      agent_id: 'c_lawd',
      channel: 'scenario',
      provider,
      model,
      reason_tag: scenario.reason,
      prompt_chars: shape.char_count_total,
      tool_output_chars: effectiveToolChars,
      tokens_in: tokensIn,
      tokens_out: tokensOut,
      total_tokens: totalTokens,
      cache_read_tokens: 0,
      cache_write_tokens: 0,
      latency_ms: mode === 'before' ? 1450 : (scenario.forceFallback ? 1250 : 820),
      status: 'ok',
      prompt_hash: hashHex(JSON.stringify(effectiveMessages))
    });
  }
  return rows;
}

function writeJsonl(filePath, rows) {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
  const lines = rows.map((row) => JSON.stringify(row)).join('\n');
  fs.writeFileSync(filePath, `${lines}\n`, 'utf8');
}

function sumTotalTokens(rows) {
  return rows.reduce((sum, row) => sum + (Number(row.total_tokens) || 0), 0);
}

function main() {
  const args = parseArgs(process.argv);
  const beforeRows = simulateMode('before', `${args.runId}_before`);
  const afterRows = simulateMode('after', `${args.runId}_after`);

  writeJsonl(args.before, beforeRows);
  writeJsonl(args.after, afterRows);

  const beforeTotal = sumTotalTokens(beforeRows);
  const afterTotal = sumTotalTokens(afterRows);
  const delta = beforeTotal - afterTotal;
  const pct = beforeTotal > 0 ? ((delta / beforeTotal) * 100).toFixed(2) : '0.00';

  console.log(`before_path=${args.before}`);
  console.log(`after_path=${args.after}`);
  console.log(`before_total_tokens=${beforeTotal}`);
  console.log(`after_total_tokens=${afterTotal}`);
  console.log(`delta_tokens=${delta}`);
  console.log(`delta_percent=${pct}`);
}

main();

