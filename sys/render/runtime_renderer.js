'use strict';

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function applyInlineFormatting(text) {
  let output = escapeHtml(text);
  output = output.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  output = output.replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2">$1</a>');
  return output;
}

function markdownToHtml(markdown) {
  const lines = String(markdown || '').replace(/\r\n/g, '\n').split('\n');
  const htmlLines = [];

  lines.forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) {
      return;
    }

    if (trimmed.startsWith('### ')) {
      htmlLines.push(`<h3>${applyInlineFormatting(trimmed.slice(4))}</h3>`);
      return;
    }
    if (trimmed.startsWith('## ')) {
      htmlLines.push(`<h2>${applyInlineFormatting(trimmed.slice(3))}</h2>`);
      return;
    }
    if (trimmed.startsWith('# ')) {
      htmlLines.push(`<h1>${applyInlineFormatting(trimmed.slice(2))}</h1>`);
      return;
    }
    if (trimmed.startsWith('- ')) {
      htmlLines.push(`<li>${applyInlineFormatting(trimmed.slice(2))}</li>`);
      return;
    }

    htmlLines.push(`<p>${applyInlineFormatting(trimmed)}</p>`);
  });

  const grouped = [];
  let openList = false;

  htmlLines.forEach((line) => {
    if (line.startsWith('<li>')) {
      if (!openList) {
        grouped.push('<ul>');
        openList = true;
      }
      grouped.push(line);
      return;
    }

    if (openList) {
      grouped.push('</ul>');
      openList = false;
    }
    grouped.push(line);
  });

  if (openList) {
    grouped.push('</ul>');
  }

  return grouped.join('\n');
}

module.exports = {
  markdownToHtml,
  escapeHtml
};
