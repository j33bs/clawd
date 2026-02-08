const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const DEFAULT_MAX_CONSTITUTION_CHARS = 8000;
const TRUNCATION_MARKER = '\n...[TRUNCATED]...\n';
const DEFAULT_CONSTITUTION_SOURCE_PATH = path.resolve(
  process.cwd(),
  'SELF_IMPROVEMENT_CONSTITUTION.md'
);
const DEFAULT_SUPPORTING_SOURCE_PATHS = [
  path.resolve(process.cwd(), 'notes/governance/2026-02-06-change-admission-gate-self-improvement.md'),
  path.resolve(process.cwd(), 'AGENTS.md')
];

function sha256(input) {
  return crypto.createHash('sha256').update(String(input || ''), 'utf8').digest('hex');
}

function truncateDeterministic(text, maxChars) {
  const value = String(text || '');
  const cap = Number(maxChars);
  if (!Number.isFinite(cap) || cap <= 0 || value.length <= cap) {
    return {
      text: value,
      truncated: false
    };
  }

  if (cap <= TRUNCATION_MARKER.length + 2) {
    return {
      text: value.slice(0, Math.max(0, cap)),
      truncated: true
    };
  }

  const available = cap - TRUNCATION_MARKER.length;
  const head = Math.ceil(available / 2);
  const tail = Math.floor(available / 2);

  return {
    text: `${value.slice(0, head)}${TRUNCATION_MARKER}${value.slice(value.length - tail)}`,
    truncated: true
  };
}

function normalizeSourcePaths(sourcePath, supportingPaths = []) {
  const primary = sourcePath || DEFAULT_CONSTITUTION_SOURCE_PATH;
  const ordered = [primary, ...(Array.isArray(supportingPaths) ? supportingPaths : [])]
    .filter(Boolean)
    .map((entry) => path.resolve(String(entry)));

  const deduped = [];
  const seen = new Set();
  ordered.forEach((entry) => {
    if (!seen.has(entry)) {
      seen.add(entry);
      deduped.push(entry);
    }
  });

  return deduped;
}

function loadSourceFile(sourcePath) {
  const content = fs.readFileSync(sourcePath, 'utf8');
  const trimmed = content.trim();
  return {
    path: sourcePath,
    text: trimmed,
    sha256: sha256(trimmed),
    approxChars: trimmed.length,
    truncated: false
  };
}

function composeSources(sources = []) {
  return sources
    .map((source) => `[SOURCE ${source.path}]\n${source.text}`)
    .join('\n\n');
}

function loadConstitutionSources({
  sourcePath = DEFAULT_CONSTITUTION_SOURCE_PATH,
  supportingPaths = DEFAULT_SUPPORTING_SOURCE_PATHS,
  maxChars = DEFAULT_MAX_CONSTITUTION_CHARS
} = {}) {
  const orderedPaths = normalizeSourcePaths(sourcePath, supportingPaths);
  const loaded = orderedPaths.map(loadSourceFile);
  const composed = composeSources(loaded);
  const truncated = truncateDeterministic(composed, maxChars);

  return {
    text: truncated.text,
    sha256: sha256(truncated.text),
    approxChars: truncated.text.length,
    truncated: truncated.truncated,
    sources: loaded.map((source) => ({
      path: source.path,
      sha256: source.sha256,
      approxChars: source.approxChars,
      truncated: source.truncated
    }))
  };
}

function buildConstitutionBlock({ text = '', sha256: digest = '', truncated = false } = {}) {
  return [
    `[CONSTITUTION_BEGIN sha256=${digest} truncated=${truncated ? 1 : 0}]`,
    String(text || ''),
    '[CONSTITUTION_END]'
  ].join('\n');
}

function buildConstitutionAuditRecord({ phase = 'constitution_instantiated', runId = null, constitution }) {
  const snapshot = constitution && typeof constitution === 'object' ? constitution : {};
  const sourceEntries = Array.isArray(snapshot.sources) ? snapshot.sources : [];
  return {
    ts: Date.now(),
    phase,
    runId,
    sha256: snapshot.sha256 || null,
    approxChars: Number(snapshot.approxChars || 0),
    truncated: Boolean(snapshot.truncated),
    sourceCount: sourceEntries.length,
    sources: sourceEntries.map((entry) => ({
      path: entry.path,
      sha256: entry.sha256 || null,
      approxChars: Number(entry.approxChars || 0),
      truncated: Boolean(entry.truncated)
    }))
  };
}

function appendConstitutionAudit(record, { rootDir = process.cwd() } = {}) {
  const dir = path.join(rootDir, 'logs');
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, 'constitution_audit.jsonl');
  fs.appendFileSync(file, `${JSON.stringify(record)}\n`, 'utf8');
}

module.exports = {
  DEFAULT_MAX_CONSTITUTION_CHARS,
  DEFAULT_CONSTITUTION_SOURCE_PATH,
  DEFAULT_SUPPORTING_SOURCE_PATHS,
  TRUNCATION_MARKER,
  sha256,
  loadConstitutionSources,
  buildConstitutionBlock,
  buildConstitutionAuditRecord,
  appendConstitutionAudit
};
