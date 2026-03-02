#!/usr/bin/env node
/**
 * Simple HTTP Chat Server for AI-to-AI Communication
 * Listens on Tailscale IP:PORT, accepts POST messages, serves GET for polling
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 8765;
const MESSAGE_FILE = '/Users/heathyeager/clawd/workspace/governance/ai_chat_messages.jsonl';

function log(who, msg) {
  const entry = { ts: new Date().toISOString(), who, msg };
  fs.appendFileSync(MESSAGE_FILE, JSON.stringify(entry) + '\n');
  console.log(`[${entry.ts}] ${who}: ${msg}`);
}

function getMessages(since) {
  if (!fs.existsSync(MESSAGE_FILE)) return [];
  const lines = fs.readFileSync(MESSAGE_FILE, 'utf8').split('\n').filter(Boolean);
  return lines
    .map(l => { try { return JSON.parse(l); } catch { return null; } })
    .filter(m => m && m.ts > since);
}

const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  const url = new URL(req.url, `http://${req.headers.host}`);

  if (req.method === 'POST' && url.pathname === '/say') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        const { who, msg } = JSON.parse(body);
        log(who || 'unknown', msg || '');
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true }));
      } catch (e) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  if (req.method === 'GET' && url.pathname === '/messages') {
    const since = url.searchParams.get('since') || '1970-01-01T00:00:00Z';
    const msgs = getMessages(since);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ messages: msgs }));
    return;
  }

  if (req.method === 'GET' && url.pathname === '/ping') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: true, ts: new Date().toISOString() }));
    return;
  }

  res.writeHead(404);
  res.end('Not Found');
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`🤖 AI Chat Server running on http://0.0.0.0:${PORT}`);
  console.log(`   Tailscale accessible at: http://100.84.143.50:${PORT}`);
  console.log(`   Endpoints:`);
  console.log(`   - POST /say {"who":"c_lawd","msg":"hello"}`);
  console.log(`   - GET /messages?since=2026-03-02T21:40:00Z`);
  console.log(`   - GET /ping`);
});
