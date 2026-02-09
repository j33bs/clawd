'use strict';

function run(context = {}) {
  const markdown = String(context.markdown || '');
  const openBrackets = (markdown.match(/\[/g) || []).length;
  const closeBrackets = (markdown.match(/\]/g) || []).length;
  const openParens = (markdown.match(/\(/g) || []).length;
  const closeParens = (markdown.match(/\)/g) || []).length;

  return {
    name: 'syntax_lint_prebrief',
    ok: openBrackets === closeBrackets && openParens === closeParens,
    diagnostics: {
      openBrackets,
      closeBrackets,
      openParens,
      closeParens
    }
  };
}

module.exports = { run };
