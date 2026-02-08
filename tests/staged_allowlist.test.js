#!/usr/bin/env node
'use strict';

const assert = require('assert');
const { spawnSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

function run(cmd, opts = {}) {
  const res = spawnSync(cmd, { shell: true, encoding: 'utf8', ...opts });
  return { code: res.status ?? 0, out: (res.stdout || '').trim(), err: (res.stderr || '').trim() };
}

function write(p, content) {
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, content, 'utf8');
}

function main() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'clawd-allowlist-test-'));
  const repo = process.cwd();

  // Minimal repo clone via worktree-style copy is overkill; we run against current repo logic,
  // but we isolate git index via a temporary gitdir+worktree using `git -C`.
  // Approach: create a throwaway git worktree to stage files without touching the main index.

  // Create worktree
  const wt = path.join(tmp, 'wt');
  const r1 = run(`git worktree add --detach "${wt}" HEAD`);
  assert.strictEqual(r1.code, 0, `worktree add failed: ${r1.err || r1.out}`);

  try {
    // Ensure clean
    const s0 = run(`git -C "${wt}" status --porcelain`);
    assert.strictEqual(s0.out, '', `worktree not clean: ${s0.out}`);

    // Create staged set representative of merge/support docs in sensitive context:
    // - include core/ to trigger enforcement context
    // - include .gitignore, docs/design, notes/governance change-admission-gate doc
    // - include self-edit of the allowlist script
    write(path.join(wt, 'core/_allowlist_probe.js'), '// probe\n');
    write(path.join(wt, '.gitignore'), 'logs/\n');
    write(path.join(wt, 'docs/design/_probe.md'), '# probe\n');
    write(path.join(wt, 'notes/governance/2026-02-08-change-admission-gate-probe.md'), '# probe\n');
    // Ensure allowlist script exists in repo; touch it via whitespace-safe append in worktree
    const allowlistPath = path.join(wt, 'scripts/check_staged_allowlist.js');
    assert.ok(fs.existsSync(allowlistPath), 'scripts/check_staged_allowlist.js missing in worktree');
    fs.appendFileSync(allowlistPath, '\n', 'utf8');

    // Stage all
    const add = run(`git -C "${wt}" add core/_allowlist_probe.js .gitignore docs/design/_probe.md notes/governance/2026-02-08-change-admission-gate-probe.md scripts/check_staged_allowlist.js`);
    assert.strictEqual(add.code, 0, `git add failed: ${add.err || add.out}`);

    // Run the checker directly (should PASS: exit 0)
    const chk = run(`node "${path.join(wt, 'scripts/check_staged_allowlist.js')}"`, { cwd: wt });
    assert.strictEqual(chk.code, 0, `allowlist check failed unexpectedly:\n${chk.err}\n${chk.out}`);

    // Negative test: stage a disallowed file and ensure it FAILS (exit 1)
    write(path.join(wt, 'random_unallowed.txt'), 'nope\n');
    const add2 = run(`git -C "${wt}" add random_unallowed.txt`);
    assert.strictEqual(add2.code, 0, `git add2 failed: ${add2.err || add2.out}`);

    const chk2 = run(`node "${path.join(wt, 'scripts/check_staged_allowlist.js')}"`, { cwd: wt });
    assert.notStrictEqual(chk2.code, 0, 'allowlist check should have failed for disallowed file');
    assert.ok(
      (chk2.err + '\n' + chk2.out).includes('random_unallowed.txt'),
      'expected offender to be reported'
    );

    console.log('PASS staged allowlist permits governance/support files in sensitive context');
    console.log('PASS staged allowlist rejects non-allowlisted paths');
  } finally {
    // Cleanup worktree (force)
    run(`git worktree remove --force "${wt}"`);
  }
}

main();
