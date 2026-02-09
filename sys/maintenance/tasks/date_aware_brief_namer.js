'use strict';

function run(context = {}) {
  const date = new Date(context.now || Date.now());
  const dateStamp = date.toISOString().slice(0, 10);
  const prefix = context.prefix || 'brief';
  return {
    name: 'date_aware_brief_namer',
    fileName: `${dateStamp}-${prefix}.md`
  };
}

module.exports = { run };
