const assert = require('node:assert');
const path = require('node:path');

const { render, clearTemplateCache, markdownToHtml } = require('../sys/render');

function run(name, fn) {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    console.error(error.message);
    process.exit(1);
  }
}

run('markdown renderer is deterministic', () => {
  const input = '# Title\n\n- One\n- Two\n\nA [link](https://example.com)';
  const first = markdownToHtml(input);
  const second = markdownToHtml(input);
  assert.strictEqual(first, second);
  assert.ok(first.includes('<h1>Title</h1>'));
  assert.ok(first.includes('<ul>'));
});

run('template render pipeline returns markdown and html', () => {
  clearTemplateCache();
  const payload = {
    title: 'Daily Brief',
    date: '2026-02-09',
    summary: 'System evolution progress snapshot.',
    highlights: {
      first: 'Config loader integrated',
      second: 'Memory graph operational'
    },
    notes: 'No regressions detected.'
  };

  const md = render({
    template: 'brief',
    format: 'markdown',
    data: payload,
    templatesDir: path.join(process.cwd(), 'sys', 'templates')
  });

  const html = render({
    template: 'brief',
    format: 'html',
    data: payload,
    templatesDir: path.join(process.cwd(), 'sys', 'templates')
  });

  assert.strictEqual(md.format, 'markdown');
  assert.ok(md.output.includes('# Daily Brief'));
  assert.strictEqual(html.format, 'html');
  assert.ok(html.output.includes('<h1>Daily Brief</h1>'));
  assert.ok(html.output.includes('<li>Config loader integrated</li>'));
});
