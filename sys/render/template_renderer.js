'use strict';

const fs = require('node:fs');
const path = require('node:path');

const templateCache = new Map();

function getValue(data, dottedPath) {
  const segments = dottedPath.split('.').map((segment) => segment.trim()).filter(Boolean);
  let cursor = data;
  for (const segment of segments) {
    if (cursor == null || typeof cursor !== 'object') {
      return '';
    }
    cursor = cursor[segment];
  }
  if (cursor == null) {
    return '';
  }
  if (typeof cursor === 'object') {
    return JSON.stringify(cursor);
  }
  return String(cursor);
}

function compileTemplate(source) {
  return function render(data) {
    return source.replace(/{{\s*([a-zA-Z0-9_.-]+)\s*}}/g, (_match, token) => getValue(data, token));
  };
}

function resolveTemplatePath(templateName, templatesDir) {
  const fileName = templateName.endsWith('.hbs') ? templateName : `${templateName}.hbs`;
  return path.join(templatesDir, fileName);
}

function loadCompiledTemplate(templateName, options = {}) {
  const templatesDir = options.templatesDir || path.join(process.cwd(), 'sys', 'templates');
  const templatePath = resolveTemplatePath(templateName, templatesDir);
  const stat = fs.statSync(templatePath);
  const cacheKey = `${templatePath}:${stat.mtimeMs}`;

  if (templateCache.has(cacheKey)) {
    return templateCache.get(cacheKey);
  }

  const source = fs.readFileSync(templatePath, 'utf8');
  const compiled = compileTemplate(source);
  templateCache.clear();
  templateCache.set(cacheKey, compiled);
  return compiled;
}

function renderTemplate(templateName, data, options = {}) {
  const compiled = loadCompiledTemplate(templateName, options);
  return compiled(data || {});
}

function clearTemplateCache() {
  templateCache.clear();
}

module.exports = {
  renderTemplate,
  clearTemplateCache,
  loadCompiledTemplate
};
