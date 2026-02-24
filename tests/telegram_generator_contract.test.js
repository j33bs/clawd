#!/usr/bin/env node
'use strict';

const { execSync } = require('node:child_process');
const { readdirSync, statSync, readFileSync, existsSync } = require('node:fs');
const path = require('node:path');

function walk(dir) {
  const out = [];
  for (const ent of readdirSync(dir)) {
    const p = path.join(dir, ent);
    const st = statSync(p);
    if (st.isDirectory()) out.push(...walk(p));
    else out.push(p);
  }
  return out;
}

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

const roots = ['/tmp/openclaw', '.runtime/openclaw/dist'];

execSync('bash workspace/scripts/rebuild_runtime_openclaw.sh', { stdio: 'inherit' });

const rootFindings = [];
const allCandidates = [];
for (const root of roots) {
  if (!existsSync(root)) {
    rootFindings.push({ root, exists: false, candidates: [] });
    continue;
  }
  const files = walk(root).filter((f) => f.endsWith('.js') || f.endsWith('.mjs') || f.endsWith('.cjs'));
  const candidates = [];
  for (const f of files) {
    const s = readFileSync(f, 'utf8');
    if (
      s.includes('telegram') &&
      s.includes('telegram_handler_deferred') &&
      s.includes('appendTelegramDeadletter')
    ) {
      candidates.push(f);
    }
  }
  rootFindings.push({ root, exists: true, candidates });
  allCandidates.push(...candidates);
}

assert(allCandidates.length > 0, 'no generated telegram handler artifacts found in scanned roots');

for (const f of allCandidates) {
  const s = readFileSync(f, 'utf8');
  const deadletterStart = s.indexOf('function appendTelegramDeadletter');
  const deadletterEnd = deadletterStart >= 0 ? s.indexOf('function isRetryableTelegramSendError', deadletterStart) : -1;
  const deadletterSlice = deadletterStart >= 0 && deadletterEnd > deadletterStart ? s.slice(deadletterStart, deadletterEnd) : s;
  assert(
    !deadletterSlice.includes('mkdirSync('),
    `mkdirSync still present in deadletter writer block: ${f}`
  );
  assert(
    !deadletterSlice.includes('appendFileSync('),
    `appendFileSync still present in deadletter writer block: ${f}`
  );

  const hasPromises =
    deadletterSlice.includes('node:fs/promises') ||
    deadletterSlice.includes('fs/promises') ||
    deadletterSlice.includes('await fs$1.mkdir(') ||
    deadletterSlice.includes('await fs$1.appendFile(');
  assert(hasPromises, `fs/promises-based deadletter write not detectable in: ${f}`);

  assert(
    s.includes('telegram_handler_deferred'),
    `defer logging key telegram_handler_deferred missing in: ${f}`
  );

  const hasHeavyMarkers =
    s.toLowerCase().includes('arxiv') ||
    s.toLowerCase().includes('.pdf') ||
    s.toLowerCase().includes('heavy') ||
    s.toLowerCase().includes('defer');
  assert(hasHeavyMarkers, `heavy/defer detection markers missing in: ${f}`);
}

console.log('generator roots scanned:');
for (const finding of rootFindings) {
  console.log(`- ${finding.root}: exists=${finding.exists} candidates=${finding.candidates.length}`);
  for (const file of finding.candidates) {
    console.log(`  - ${file}`);
  }
}
console.log('PASS: telegram generator contract');
