'use strict';

const { markdownToHtml } = require('./runtime_renderer');
const { renderTemplate, clearTemplateCache } = require('./template_renderer');

function render(options = {}) {
  const template = options.template || null;
  const format = options.format || 'markdown';
  const data = options.data || {};

  const markdown = template ? renderTemplate(template, data, options) : String(options.markdown || data.markdown || '');

  if (format === 'html') {
    return {
      format: 'html',
      output: markdownToHtml(markdown),
      markdown
    };
  }

  return {
    format: 'markdown',
    output: markdown,
    markdown
  };
}

module.exports = {
  render,
  renderTemplate,
  markdownToHtml,
  clearTemplateCache
};
