"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { requireSubprocessOrSkip } = require("../../../../tests/helpers/capabilities");

function run(cmd, args, cwd) {
  const out = spawnSync(cmd, args, { cwd, encoding: "utf8" });
  return out;
}

function initTempRepo() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "scaffold-apply-test-"));
  run("git", ["init"], dir);
  run("git", ["config", "user.email", "skill-test@example.com"], dir);
  run("git", ["config", "user.name", "Skill Test"], dir);
  fs.writeFileSync(path.join(dir, "a.txt"), "hello\n", "utf8");
  run("git", ["add", "a.txt"], dir);
  run("git", ["commit", "-m", "init"], dir);
  return dir;
}

test("dry-run patch check passes on valid patch", (t) => {
  if (!requireSubprocessOrSkip(t)) {
    return;
  }

  const repo = initTempRepo();
  const file = path.join(repo, "a.txt");
  fs.writeFileSync(file, "hello world\n", "utf8");
  const diff = run("git", ["diff", "--", "a.txt"], repo).stdout;
  run("git", ["checkout", "--", "a.txt"], repo);

  const input = {
    dry_run: true,
    target_dir: repo,
    plan: [
      {
        file: "a.txt",
        operation: "patch",
        content: diff,
        rationale: "update content"
      }
    ]
  };

  const cli = path.join(__dirname, "..", "dist", "cli.js");
  const proc = spawnSync("node", [cli], {
    input: JSON.stringify(input),
    encoding: "utf8",
  });

  assert.equal(proc.status, 0, proc.stdout + proc.stderr);
  const out = JSON.parse(proc.stdout.trim());
  assert.equal(out.steps_failed, 0);
});

test("dry-run patch check reports failed step on invalid patch", (t) => {
  if (!requireSubprocessOrSkip(t)) {
    return;
  }

  const repo = initTempRepo();
  const input = {
    dry_run: true,
    target_dir: repo,
    plan: [
      {
        file: "a.txt",
        operation: "patch",
        content: "not a unified diff",
        rationale: "bad patch"
      }
    ]
  };

  const cli = path.join(__dirname, "..", "dist", "cli.js");
  const proc = spawnSync("node", [cli], {
    input: JSON.stringify(input),
    encoding: "utf8",
  });

  assert.equal(proc.status, 1, proc.stdout + proc.stderr);
  const out = JSON.parse(proc.stdout.trim());
  assert.equal(out.steps_failed, 1);
  assert.equal(out.failed_step.index, 0);
});
