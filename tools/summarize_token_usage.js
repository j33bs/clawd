#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

function usage() {
  console.error('Usage: node tools/summarize_token_usage.js [jsonl_path]');
  process.exit(2);
}

function toNum(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function pad(value, width) {
  const text = String(value);
  if (text.length >= width) return text.slice(0, width);
  return text + ' '.repeat(width - text.length);
}

function readJsonl(filePath) {
  const raw = fs.readFileSync(filePath, 'utf8');
  const rows = [];
  for (const line of raw.split(/\r?\n/)) {
    const t = line.trim();
    if (!t) continue;
    try {
      rows.push(JSON.parse(t));
    } catch (_) {
      // Ignore malformed lines.
    }
  }
  return rows;
}

function main() {
  const arg = process.argv[2];
  if (arg === '-h' || arg === '--help') usage();

  const inputPath = path.resolve(arg || process.env.OPENCLAW_TOKEN_USAGE_LOG_PATH || path.join('workspace', 'logs', 'token_usage.jsonl'));
  if (!fs.existsSync(inputPath)) {
    console.error(`token usage log not found: ${inputPath}`);
    process.exit(1);
  }

  const rows = readJsonl(inputPath);
  if (rows.length === 0) {
    console.log(`Input: ${inputPath}`);
    console.log('No records.');
    return;
  }

  let totalIn = 0;
  let totalOut = 0;
  let totalTokens = 0;
  let totalPromptChars = 0;
  let totalToolChars = 0;
  const statusCounts = new Map();
  const grouped = new Map();

  for (const row of rows) {
    const tokensIn = toNum(row.tokens_in);
    const tokensOut = toNum(row.tokens_out);
    const tokensTotal = toNum(row.total_tokens) || (tokensIn + tokensOut);
    const promptChars = toNum(row.prompt_chars);
    const toolChars = toNum(row.tool_output_chars);

    totalIn += tokensIn;
    totalOut += tokensOut;
    totalTokens += tokensTotal;
    totalPromptChars += promptChars;
    totalToolChars += toolChars;

    const status = String(row.status || 'unknown');
    statusCounts.set(status, (statusCounts.get(status) || 0) + 1);

    const provider = String(row.provider || 'unknown');
    const model = String(row.model || 'unknown');
    const reason = String(row.reason_tag || 'unknown');
    const key = `${provider}|||${model}|||${reason}`;
    if (!grouped.has(key)) {
      grouped.set(key, {
        provider,
        model,
        reason_tag: reason,
        requests: 0,
        tokens_in: 0,
        tokens_out: 0,
        total_tokens: 0,
        prompt_chars: 0,
        tool_output_chars: 0
      });
    }
    const g = grouped.get(key);
    g.requests += 1;
    g.tokens_in += tokensIn;
    g.tokens_out += tokensOut;
    g.total_tokens += tokensTotal;
    g.prompt_chars += promptChars;
    g.tool_output_chars += toolChars;
  }

  const groupRows = Array.from(grouped.values()).sort((a, b) => b.total_tokens - a.total_tokens);
  const topRequests = rows
    .map((r) => ({
      ts_utc: String(r.ts_utc || ''),
      request_id: String(r.request_id || ''),
      provider: String(r.provider || 'unknown'),
      model: String(r.model || 'unknown'),
      reason_tag: String(r.reason_tag || 'unknown'),
      total_tokens: toNum(r.total_tokens) || (toNum(r.tokens_in) + toNum(r.tokens_out)),
      status: String(r.status || 'unknown')
    }))
    .sort((a, b) => b.total_tokens - a.total_tokens)
    .slice(0, 20);

  console.log(`Input: ${inputPath}`);
  console.log(`Records: ${rows.length}`);
  console.log(`Totals: tokens_in=${totalIn} tokens_out=${totalOut} total_tokens=${totalTokens} prompt_chars=${totalPromptChars} tool_output_chars=${totalToolChars}`);
  console.log(`Status counts: ${Array.from(statusCounts.entries()).map(([k, v]) => `${k}=${v}`).join(', ')}`);
  console.log('');
  console.log('By provider/model/reason_tag');
  console.log(
    [
      pad('provider', 16),
      pad('model', 30),
      pad('reason_tag', 16),
      pad('req', 6),
      pad('tokens', 10),
      pad('prompt_chars', 12),
      pad('tool_chars', 10)
    ].join(' ')
  );
  for (const row of groupRows) {
    console.log(
      [
        pad(row.provider, 16),
        pad(row.model, 30),
        pad(row.reason_tag, 16),
        pad(row.requests, 6),
        pad(row.total_tokens, 10),
        pad(row.prompt_chars, 12),
        pad(row.tool_output_chars, 10)
      ].join(' ')
    );
  }

  console.log('');
  console.log('Top 20 largest requests (by total_tokens)');
  console.log(
    [
      pad('total_tokens', 12),
      pad('provider', 12),
      pad('model', 24),
      pad('reason', 14),
      pad('status', 14),
      'request_id'
    ].join(' ')
  );
  for (const row of topRequests) {
    console.log(
      [
        pad(row.total_tokens, 12),
        pad(row.provider, 12),
        pad(row.model, 24),
        pad(row.reason_tag, 14),
        pad(row.status, 14),
        row.request_id
      ].join(' ')
    );
  }
}

main();

