'use strict';

const fs = require('node:fs');
const path = require('node:path');

const CODE_EXTENSIONS = Object.freeze(['.js', '.cjs', '.mjs', '.ts']);
const INDEX_EXTENSIONS = Object.freeze(['.js', '.cjs', '.mjs']);
const EXCLUDED_DIRS = new Set(['.git', 'node_modules']);

function toPosix(value) {
  return String(value || '').split(path.sep).join('/');
}

function isCodeFile(filePath) {
  return CODE_EXTENSIONS.includes(path.extname(filePath));
}

function collectCodeFiles(rootDir, currentDir = rootDir) {
  const entries = fs.readdirSync(currentDir, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    if (entry.name.startsWith('.') && entry.name !== '.github') {
      if (entry.name !== '.eslintrc' && entry.name !== '.npmrc') {
        continue;
      }
    }

    const fullPath = path.join(currentDir, entry.name);
    if (entry.isDirectory()) {
      if (EXCLUDED_DIRS.has(entry.name)) {
        continue;
      }
      files.push(...collectCodeFiles(rootDir, fullPath));
      continue;
    }
    if (entry.isFile() && isCodeFile(fullPath)) {
      files.push(fullPath);
    }
  }

  files.sort((a, b) => toPosix(path.relative(rootDir, a)).localeCompare(toPosix(path.relative(rootDir, b))));
  return files;
}

function parseRelativeSpecifiers(source) {
  const matches = [];
  const patterns = [
    /require\(\s*['"](\.{1,2}\/[^'"]+)['"]\s*\)/g,
    /import\s+[^'"]*?\s+from\s+['"](\.{1,2}\/[^'"]+)['"]/g,
    /import\(\s*['"](\.{1,2}\/[^'"]+)['"]\s*\)/g
  ];

  for (const basePattern of patterns) {
    const pattern = new RegExp(basePattern.source, 'g');
    let match;
    while ((match = pattern.exec(source)) !== null) {
      matches.push(match[1]);
    }
  }

  return matches;
}

function unique(values) {
  return Array.from(new Set(values));
}

function resolveCandidates(filePath, specifier) {
  const base = path.resolve(path.dirname(filePath), specifier);
  const direct = [base];
  const ext = CODE_EXTENSIONS.map((suffix) => `${base}${suffix}`);
  const index = INDEX_EXTENSIONS.map((suffix) => path.join(base, `index${suffix}`));
  return unique([...direct, ...ext, ...index]);
}

function existingCandidates(candidates) {
  return candidates.filter((candidate) => {
    try {
      return fs.statSync(candidate).isFile();
    } catch (_) {
      return false;
    }
  });
}

function summarize(rootDir = process.cwd()) {
  const files = collectCodeFiles(rootDir);
  const findings = [];

  for (const filePath of files) {
    const source = fs.readFileSync(filePath, 'utf8');
    const specifiers = parseRelativeSpecifiers(source);
    for (const specifier of specifiers) {
      const candidates = resolveCandidates(filePath, specifier);
      const hits = existingCandidates(candidates);
      if (hits.length > 0) {
        continue;
      }
      findings.push({
        file: toPosix(path.relative(rootDir, filePath)),
        specifier,
        resolvedCandidates: candidates.map((candidate) => toPosix(path.relative(rootDir, candidate)))
      });
    }
  }

  findings.sort((a, b) => {
    const fileCmp = a.file.localeCompare(b.file);
    if (fileCmp !== 0) {
      return fileCmp;
    }
    return a.specifier.localeCompare(b.specifier);
  });

  return {
    findings_count: findings.length,
    findings
  };
}

function main() {
  try {
    const result = summarize(process.cwd());
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    process.exit(result.findings_count > 0 ? 2 : 0);
  } catch (error) {
    const payload = {
      findings_count: null,
      findings: [],
      error: {
        name: error && error.name ? error.name : 'Error',
        message: error && error.message ? error.message : String(error)
      }
    };
    process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
    process.exit(3);
  }
}

module.exports = {
  summarize,
  parseRelativeSpecifiers,
  resolveCandidates
};

if (require.main === module) {
  main();
}
