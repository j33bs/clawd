'use strict';

function run(context = {}) {
  const markdown = String(context.markdown || '');
  const normalized = markdown.replace(/\]\(([^):]+)\)/g, (_match, link) => {
    const trimmed = String(link).trim();
    if (trimmed.startsWith('./') || trimmed.startsWith('../') || trimmed.startsWith('http')) {
      return `](${trimmed})`;
    }
    return `](./${trimmed})`;
  });

  return {
    name: 'markdown_link_normalizer',
    changed: normalized !== markdown,
    normalized
  };
}

module.exports = { run };
