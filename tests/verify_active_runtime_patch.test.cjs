#!/usr/bin/env node
'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const { execSync } = require('node:child_process');

const REQUIRED_MARKERS = [
  'MAX_SYSTEM_PROMPT_CHARS',
  'STRICT_MAX_SYSTEM_PROMPT_CHARS',
  'embedded_prompt_before',
  'embedded_attempt',
  'projectContextIncludedChars'
];

function findMissingMarkers(text, markers) {
  return markers.filter((m) => !text.includes(m));
}

function lineNumberOf(text, marker) {
  const idx = text.indexOf(marker);
  if (idx === -1) return -1;
  let line = 1;
  for (let i = 0; i < idx; i += 1) if (text.charCodeAt(i) === 10) line += 1;
  return line;
}

function resolveActivePackageDir() {
  const cliPath = execSync('which openclaw', { encoding: 'utf8' }).trim();
  assert.ok(cliPath, 'openclaw not found in PATH');
  const launcherPath = fs.realpathSync(cliPath);
  return path.dirname(launcherPath);
}

function main() {
  const activePackageDir = resolveActivePackageDir();
  const activeLoaderPath = path.join(activePackageDir, 'dist', 'loader-BAZoAqqR.js');
  assert.ok(fs.existsSync(activeLoaderPath), `active loader not found: ${activeLoaderPath}`);

  const text = fs.readFileSync(activeLoaderPath, 'utf8');
  const missing = findMissingMarkers(text, REQUIRED_MARKERS);
  assert.deepStrictEqual(missing, [], `missing required markers: ${missing.join(', ')}`);

  // simulate exact-token removal; must truly remove the marker
  const missingSimText = text.replace('"embedded_attempt"', '"EMBEDDED_ATTEMPT_REMOVED"');
  const missingSim = findMissingMarkers(missingSimText, REQUIRED_MARKERS);
  assert.ok(missingSim.includes('embedded_attempt'), 'simulated missing marker should include embedded_attempt');

  console.log('ACTIVE_PACKAGE_DIR=' + activePackageDir);
  console.log('ACTIVE_LOADER=' + activeLoaderPath);
  for (const marker of REQUIRED_MARKERS) console.log(`MARKER_${marker}=line:${lineNumberOf(text, marker)}`);
  console.log('RESULT=PASS');
}

main();
