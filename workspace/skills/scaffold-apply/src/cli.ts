import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { validatePlanInput } from "./plan_schema";

type Step = {
  file: string;
  operation: "create" | "patch" | "delete";
  content?: string;
  rationale: string;
};

type PlanInput = { dry_run?: boolean; target_dir: string; plan: Step[] };

function output(payload: Record<string, unknown>, ok: boolean): never {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
  process.exit(ok ? 0 : 1);
}

function readJsonStdin(): Promise<any> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    process.stdin.on("data", (c) => chunks.push(Buffer.from(c)));
    process.stdin.on("end", () => {
      const raw = Buffer.concat(chunks).toString("utf8").trim();
      if (!raw) {
        reject(new Error("stdin JSON is required"));
        return;
      }
      try {
        resolve(JSON.parse(raw));
      } catch (err) {
        reject(err);
      }
    });
    process.stdin.on("error", reject);
  });
}

function git(targetDir: string, args: string[]): { ok: boolean; stdout: string; stderr: string } {
  const proc = spawnSync("git", ["-C", targetDir, ...args], { encoding: "utf8" });
  return {
    ok: proc.status === 0,
    stdout: proc.stdout || "",
    stderr: proc.stderr || "",
  };
}

function ensureRepo(targetDir: string): void {
  const check = git(targetDir, ["rev-parse", "--is-inside-work-tree"]);
  if (!check.ok || !check.stdout.includes("true")) {
    output({
      steps_applied: 0,
      steps_failed: 1,
      commit_hashes: [],
      failed_step: { index: -1, step: null, error: "target_dir is not a git repo" },
    }, false);
  }
}

function resolvePathSafe(targetDir: string, relFile: string): string {
  const root = path.resolve(targetDir);
  const full = path.resolve(root, relFile);
  if (!(full === root || full.startsWith(root + path.sep))) {
    throw new Error(`path traversal blocked: ${relFile}`);
  }
  return full;
}

function writeTempPatch(content: string): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "scaffold-apply-"));
  const patchPath = path.join(dir, "step.patch");
  fs.writeFileSync(patchPath, content, "utf8");
  return patchPath;
}

function dryRunStep(targetDir: string, step: Step): void {
  const abs = resolvePathSafe(targetDir, step.file);
  if (step.operation === "create") {
    if (fs.existsSync(abs)) throw new Error(`create target already exists: ${step.file}`);
    return;
  }
  if (step.operation === "delete") {
    if (!fs.existsSync(abs)) throw new Error(`delete target missing: ${step.file}`);
    return;
  }
  if (step.operation === "patch") {
    const patchPath = writeTempPatch(String(step.content || ""));
    const check = git(targetDir, ["apply", "--check", "--whitespace=nowarn", patchPath]);
    if (!check.ok) throw new Error(`patch check failed: ${check.stderr.trim()}`);
    return;
  }
}

function applyStep(targetDir: string, step: Step): void {
  const abs = resolvePathSafe(targetDir, step.file);
  if (step.operation === "create") {
    if (fs.existsSync(abs)) throw new Error(`create target already exists: ${step.file}`);
    fs.mkdirSync(path.dirname(abs), { recursive: true });
    fs.writeFileSync(abs, String(step.content || ""), "utf8");
    const add = git(targetDir, ["add", "--", step.file]);
    if (!add.ok) throw new Error(add.stderr.trim() || `git add failed: ${step.file}`);
    return;
  }
  if (step.operation === "delete") {
    if (!fs.existsSync(abs)) throw new Error(`delete target missing: ${step.file}`);
    const rm = git(targetDir, ["rm", "-f", "--", step.file]);
    if (!rm.ok) throw new Error(rm.stderr.trim() || `git rm failed: ${step.file}`);
    return;
  }
  if (step.operation === "patch") {
    const patchPath = writeTempPatch(String(step.content || ""));
    const apply = git(targetDir, ["apply", "--index", "--whitespace=nowarn", patchPath]);
    if (!apply.ok) throw new Error(`patch apply failed: ${apply.stderr.trim()}`);
    return;
  }
}

function commitStep(targetDir: string, step: Step): string {
  const msg = `scaffold: ${step.operation} ${step.file}`;
  const commit = git(targetDir, ["commit", "-m", msg, "-m", step.rationale]);
  if (!commit.ok) throw new Error(`commit failed: ${commit.stderr.trim()}`);
  const sha = git(targetDir, ["rev-parse", "--short", "HEAD"]);
  if (!sha.ok) throw new Error(`failed to read commit hash: ${sha.stderr.trim()}`);
  return sha.stdout.trim();
}

async function main(): Promise<void> {
  let inputRaw: any;
  try {
    inputRaw = await readJsonStdin();
  } catch (err) {
    output({
      steps_applied: 0,
      steps_failed: 1,
      commit_hashes: [],
      failed_step: { index: -1, step: null, error: String(err) },
    }, false);
  }

  const validation = validatePlanInput(inputRaw);
  if (!validation.valid) {
    output({
      steps_applied: 0,
      steps_failed: 1,
      commit_hashes: [],
      failed_step: { index: -1, step: null, error: validation.errors.join("; ") },
    }, false);
  }

  const input = inputRaw as PlanInput;
  const dryRun = Boolean(input.dry_run);
  const targetDir = path.resolve(input.target_dir);
  ensureRepo(targetDir);

  const commitHashes: string[] = [];
  let stepsApplied = 0;

  for (let i = 0; i < input.plan.length; i += 1) {
    const step = input.plan[i];
    try {
      if (dryRun) {
        dryRunStep(targetDir, step);
      } else {
        applyStep(targetDir, step);
        const hash = commitStep(targetDir, step);
        commitHashes.push(hash);
        stepsApplied += 1;
      }
    } catch (err) {
      output({
        steps_applied: stepsApplied,
        steps_failed: 1,
        commit_hashes: commitHashes,
        failed_step: { index: i, step, error: String(err) },
      }, false);
    }
  }

  output({
    steps_applied: stepsApplied,
    steps_failed: 0,
    commit_hashes: commitHashes,
  }, true);
}

main().catch((err) => {
  output({
    steps_applied: 0,
    steps_failed: 1,
    commit_hashes: [],
    failed_step: { index: -1, step: null, error: String(err) },
  }, false);
});
