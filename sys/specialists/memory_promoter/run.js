'use strict';

function run(context) {
  return {
    promoted: [`candidate:${context.task.id}`],
    timestamp: context.now,
    persona: context.persona.name
  };
}

module.exports = {
  run
};
