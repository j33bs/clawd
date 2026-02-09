'use strict';

function createScheduler() {
  return {
    enqueue() {
      return {
        queued: true,
        id: 'scaffold-task'
      };
    },
    runOnce() {
      return {
        ran: false,
        reason: 'scheduler scaffold (commit 1)'
      };
    }
  };
}

module.exports = {
  createScheduler
};
