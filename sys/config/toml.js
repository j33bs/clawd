'use strict';

function parseInlineArray(value) {
  const content = value.slice(1, -1).trim();
  if (!content) {
    return [];
  }

  return content
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .map(parseValue);
}

function parseValue(rawValue) {
  const value = rawValue.trim();

  if (!value) {
    return '';
  }

  if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
    return value.slice(1, -1);
  }

  if (value === 'true') {
    return true;
  }
  if (value === 'false') {
    return false;
  }

  if (value.startsWith('[') && value.endsWith(']')) {
    return parseInlineArray(value);
  }

  if (/^-?\d+(\.\d+)?$/.test(value)) {
    return Number(value);
  }

  return value;
}

function parseToml(content) {
  const root = {};
  let sectionPath = [];

  const lines = String(content || '').split(/\r?\n/);
  for (const originalLine of lines) {
    const line = originalLine.replace(/\s+#.*$/, '').trim();
    if (!line) {
      continue;
    }

    if (line.startsWith('[') && line.endsWith(']')) {
      sectionPath = line
        .slice(1, -1)
        .split('.')
        .map((segment) => segment.trim())
        .filter(Boolean);
      continue;
    }

    const separatorIndex = line.indexOf('=');
    if (separatorIndex === -1) {
      continue;
    }

    const key = line.slice(0, separatorIndex).trim();
    const rawValue = line.slice(separatorIndex + 1);
    const parsedValue = parseValue(rawValue);

    let cursor = root;
    for (const part of sectionPath) {
      if (!cursor[part] || typeof cursor[part] !== 'object' || Array.isArray(cursor[part])) {
        cursor[part] = {};
      }
      cursor = cursor[part];
    }

    cursor[key] = parsedValue;
  }

  return root;
}

module.exports = {
  parseToml,
  parseValue
};
