'use strict';

/**
 * Stable SQLite adapter for system-evolution queue storage.
 *
 * Usage:
 *   const { open } = require('../db/sqlite_adapter');
 *   const db = open('/path/to/queue.sqlite');
 */
const Database = require('better-sqlite3');

function open(dbPath, options = {}) {
  const db = new Database(dbPath, options);

  return {
    exec(sql) {
      return db.exec(sql);
    },
    prepare(sql) {
      const stmt = db.prepare(sql);
      return {
        run(params) {
          if (params === undefined) {
            return stmt.run();
          }
          return stmt.run(params);
        },
        get(params) {
          if (params === undefined) {
            return stmt.get();
          }
          return stmt.get(params);
        },
        all(params) {
          if (params === undefined) {
            return stmt.all();
          }
          return stmt.all(params);
        }
      };
    },
    close() {
      return db.close();
    }
  };
}

module.exports = {
  open
};
