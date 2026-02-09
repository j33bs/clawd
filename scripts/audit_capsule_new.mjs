#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { formatOperatorSummary } = require('../sys/audit/policy');

const OPERATOR_CONTRACT = [
  'Always run preflight: git status, branch, log, key gates.',
  'Never edit dist/runtime bundles or global installs.',
  'Never bypass governance hooks or admission gates.',
  'Keep changes minimal, reversible, and scoped.',
  'Use feature flags/env toggles for new behavior; default OFF unless additive and safe.',
  'Log only hashes, sizes, IDs, and classes; never raw sensitive content.',
  'For routing/gates/providers changes, create a change capsule and run acceptance + gate scripts.',
  'Stop on first failure; report exact command and output.',
  'Include rollback instructions in every non-trivial contribution.',
  'When blocked by policy/hooks, satisfy requirements rather than overriding.'
];

function parseArgs(argv) {
  const out = { slug: null, date: null };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--slug') {
      out.slug = argv[i + 1] || null;
      i += 1;
      continue;
    }
    if (arg.startsWith('--slug=')) {
      out.slug = arg.slice('--slug='.length);
      continue;
    }
    if (arg === '--date') {
      out.date = argv[i + 1] || null;
      i += 1;
      continue;
    }
    if (arg.startsWith('--date=')) {
      out.date = arg.slice('--date='.length);
      continue;
    }
  }
  return out;
}

function normalizeSlug(value) {
  const clean = String(value || 'change')
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64);
  return clean || 'change';
}

function isoDate(date = new Date()) {
  return date.toISOString().slice(0, 10);
}

function applyTemplate(template, values) {
  let out = template;
  for (const [key, value] of Object.entries(values)) {
    out = out.replaceAll(`__${key}__`, String(value));
  }
  return out;
}

function pickCollisionSafeBase(dir, baseName) {
  const exts = ['.md', '.json'];
  const available = (candidate) => exts.every((ext) => !fs.existsSync(path.join(dir, `${candidate}${ext}`)));
  if (available(baseName)) {
    return baseName;
  }

  for (const suffix of 'abcdefghijklmnopqrstuvwxyz') {
    const candidate = `${baseName}${suffix}`;
    if (available(candidate)) {
      return candidate;
    }
  }

  throw new Error(`no collision-safe capsule name available for ${baseName}`);
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const slug = normalizeSlug(args.slug);
  const date = args.date || isoDate();

  const root = process.cwd();
  const verifyDir = path.join(root, 'notes', 'verification');
  const templatesDir = path.join(verifyDir, 'templates');
  const mdTemplatePath = path.join(templatesDir, 'change_capsule.md.template');
  const jsonTemplatePath = path.join(templatesDir, 'change_capsule.json.template');

  if (!fs.existsSync(mdTemplatePath) || !fs.existsSync(jsonTemplatePath)) {
    console.log(formatOperatorSummary({
      changed: 'none',
      verified: [],
      blocked: `capsule templates missing in ${templatesDir}`,
      nextAction: 'restore notes/verification/templates/change_capsule.*.template'
    }));
    process.exit(1);
  }

  fs.mkdirSync(verifyDir, { recursive: true });

  const baseName = `${date}-change-capsule-${slug}`;
  const finalBase = pickCollisionSafeBase(verifyDir, baseName);

  const values = { DATE: date, SLUG: slug };
  const mdTemplate = fs.readFileSync(mdTemplatePath, 'utf8');
  const jsonTemplate = fs.readFileSync(jsonTemplatePath, 'utf8');

  const mdPath = path.join(verifyDir, `${finalBase}.md`);
  const jsonPath = path.join(verifyDir, `${finalBase}.json`);

  fs.writeFileSync(mdPath, applyTemplate(mdTemplate, values), 'utf8');
  fs.writeFileSync(jsonPath, applyTemplate(jsonTemplate, values), 'utf8');

  console.log(formatOperatorSummary({
    changed: `${path.relative(root, mdPath)}, ${path.relative(root, jsonPath)}`,
    verified: ['capsule_template', 'collision_safe_name'],
    blocked: 'none',
    nextAction: `review capsule files, then fill evidence and rollback sections`
  }));

  console.log('OPERATOR_CONTRACT_START');
  for (const line of OPERATOR_CONTRACT) {
    console.log(`- ${line}`);
  }
  console.log('OPERATOR_CONTRACT_END');
}

main();
