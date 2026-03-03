import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { assertPathWithinRoot } from '../src/security/fs_sandbox.mjs';

test('filesystem sandbox rejects path traversal escape', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'hardening-root-'));
  const target = path.join(root, '..', 'outside.txt');

  assert.throws(() => assertPathWithinRoot(root, target), /path escapes workspace root/);
});

test('filesystem sandbox rejects symlink escape', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'hardening-root-symlink-'));
  const outsideDir = fs.mkdtempSync(path.join(os.tmpdir(), 'hardening-outside-'));
  const linkPath = path.join(root, 'link');
  fs.symlinkSync(outsideDir, linkPath);

  const escaped = path.join(linkPath, 'secret.txt');
  assert.throws(() => assertPathWithinRoot(root, escaped), /path escapes workspace root/);
});
