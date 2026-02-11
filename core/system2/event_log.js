'use strict';

const fs = require('node:fs');
const path = require('node:path');

function resolveFilePath(workspaceRoot, relativeOrAbsolute) {
  if (path.isAbsolute(relativeOrAbsolute)) {
    return path.resolve(relativeOrAbsolute);
  }
  return path.resolve(workspaceRoot, relativeOrAbsolute);
}

function ensureParentDir(filePath) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
}

function withLock(filePath, fn) {
  const lockPath = `${filePath}.lock`;
  const fd = fs.openSync(lockPath, 'w');
  try {
    return fn();
  } finally {
    fs.closeSync(fd);
    fs.unlinkSync(lockPath);
  }
}

class System2EventLog {
  constructor(options = {}) {
    this.workspaceRoot = options.workspaceRoot || process.cwd();
    this.eventLogPath = resolveFilePath(
      this.workspaceRoot,
      options.eventLogPath || 'sys/state/system2/events.jsonl'
    );
    this.cursorPath = resolveFilePath(
      this.workspaceRoot,
      options.cursorPath || 'sys/state/system2/sync_cursor.json'
    );
  }

  appendEvent(event = {}) {
    const enriched = {
      ts: event.ts || new Date().toISOString(),
      ...event
    };
    ensureParentDir(this.eventLogPath);
    return withLock(this.eventLogPath, () => {
      fs.appendFileSync(this.eventLogPath, `${JSON.stringify(enriched)}\n`, 'utf8');
      return enriched;
    });
  }

  readEventsSince(cursor = null) {
    const lineStart =
      cursor && typeof cursor === 'object' && Number.isInteger(cursor.line)
        ? cursor.line
        : Number.isInteger(cursor)
          ? cursor
          : 0;

    if (!fs.existsSync(this.eventLogPath)) {
      return {
        events: [],
        nextCursor: { line: lineStart },
        totalLines: 0
      };
    }

    const lines = fs.readFileSync(this.eventLogPath, 'utf8').split('\n').filter(Boolean);
    const events = lines.slice(Math.max(0, lineStart)).map((line) => {
      try {
        return JSON.parse(line);
      } catch (_) {
        return {
          ts: new Date().toISOString(),
          event_type: 'parse_error',
          raw: line
        };
      }
    });

    return {
      events,
      nextCursor: { line: lines.length },
      totalLines: lines.length
    };
  }

  readCursor() {
    if (!fs.existsSync(this.cursorPath)) {
      return { line: 0 };
    }
    try {
      const parsed = JSON.parse(fs.readFileSync(this.cursorPath, 'utf8'));
      if (parsed && Number.isInteger(parsed.line) && parsed.line >= 0) {
        return parsed;
      }
    } catch (_) {
      return { line: 0 };
    }
    return { line: 0 };
  }

  advanceCursor(cursor = {}) {
    const next = {
      line: Number.isInteger(cursor.line) && cursor.line >= 0 ? cursor.line : 0,
      updated_at: new Date().toISOString()
    };
    ensureParentDir(this.cursorPath);
    fs.writeFileSync(this.cursorPath, `${JSON.stringify(next, null, 2)}\n`, 'utf8');
    return next;
  }

  async syncWithRemote(options = {}) {
    const pushFn = options.pushFn;
    if (typeof pushFn !== 'function') {
      throw new Error('syncWithRemote requires pushFn');
    }

    const cursor = this.readCursor();
    const batch = this.readEventsSince(cursor);
    if (batch.events.length === 0) {
      return {
        pushed: 0,
        cursor,
        nextCursor: batch.nextCursor
      };
    }

    const ack = await pushFn(batch.events, cursor);
    if (ack && ack.ok) {
      const advanced = this.advanceCursor(batch.nextCursor);
      return {
        pushed: batch.events.length,
        cursor: advanced,
        nextCursor: batch.nextCursor
      };
    }

    return {
      pushed: 0,
      cursor,
      nextCursor: cursor,
      blocked: true
    };
  }
}

module.exports = {
  System2EventLog
};
