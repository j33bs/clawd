'use strict';

function createMemoryGraphStore() {
  return {
    upsertNode() {
      throw new Error('memory_graph.upsertNode not implemented yet');
    },
    addRelation() {
      throw new Error('memory_graph.addRelation not implemented yet');
    },
    fetchRelated() {
      throw new Error('memory_graph.fetchRelated not implemented yet');
    },
    exportGraph() {
      return {
        '@context': 'https://schema.org',
        '@graph': []
      };
    }
  };
}

module.exports = {
  createMemoryGraphStore
};
