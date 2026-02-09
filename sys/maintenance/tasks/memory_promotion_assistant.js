'use strict';

function run(context = {}) {
  const candidates = Array.isArray(context.candidates) ? context.candidates : [];
  const promoted = candidates
    .filter((candidate) => candidate && candidate.score >= (context.threshold || 0.75))
    .map((candidate) => candidate.id);

  return {
    name: 'memory_promotion_assistant',
    promoted,
    threshold: context.threshold || 0.75
  };
}

module.exports = { run };
