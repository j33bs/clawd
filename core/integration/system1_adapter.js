'use strict';

const { execFile } = require('node:child_process');
const util = require('node:util');

const execFilePromise = util.promisify(execFile);
const DEFAULT_EXTERNAL_ROOT = process.env.CLAWD_EXTERNAL_ROOT || '/Users/heathyeager/clawd_external';

function pythonArgsForModule(moduleName, fnName, fnArgs = [], externalRoot = DEFAULT_EXTERNAL_ROOT) {
  const payload = JSON.stringify({ fn: fnName, args: fnArgs });
  const code =
    `import json,sys,importlib\n` +
    `root=${JSON.stringify(externalRoot)}\n` +
    `sys.path.insert(0, root)\n` +
    `req=json.loads(${JSON.stringify(payload)})\n` +
    `mod=importlib.import_module(${JSON.stringify(moduleName)})\n` +
    `fn=getattr(mod, req['fn'])\n` +
    `out=fn(*req.get('args', []))\n` +
    `print(json.dumps({'ok': True, 'result': out}, default=str))\n`;
  return ['-c', code];
}

async function callSystem1(moduleName, fnName, fnArgs = [], options = {}) {
  const python = options.python || 'python3';
  const externalRoot = options.externalRoot || DEFAULT_EXTERNAL_ROOT;

  const { stdout } = await execFilePromise(
    python,
    pythonArgsForModule(moduleName, fnName, fnArgs, externalRoot),
    {
      cwd: options.cwd || externalRoot,
      timeout: options.timeoutMs || 30000,
      maxBuffer: options.maxBuffer || 5 * 1024 * 1024
    }
  );

  const text = String(stdout || '').trim();
  try {
    return JSON.parse(text);
  } catch (_) {
    return {
      ok: false,
      error: 'NON_JSON_OUTPUT',
      raw: text
    };
  }
}

module.exports = {
  callSystem1,
  DEFAULT_EXTERNAL_ROOT
};
