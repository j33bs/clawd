'use strict';

function summary() {
  return {
    status: 'no_ingested_sources',
    message: 'No ingested sources. Run the breath ingest pipeline with local evidence files.',
    last_updated: null,
    items: []
  };
}

module.exports = {
  summary
};
