import path from 'node:path';
import { ensureDirectoryWithinRoot } from './security/fs_sandbox.mjs';

function resolveWorkspacePaths(config) {
  const workspaceRoot = path.resolve(config.workspaceRoot);
  const agentWorkspaceRoot = path.resolve(config.agentWorkspaceRoot);
  const skillsRoot = path.resolve(config.skillsRoot);

  return {
    workspaceRoot,
    agentWorkspaceRoot,
    skillsRoot
  };
}

function ensureWorkspaceDirectories(config) {
  const paths = resolveWorkspacePaths(config);
  const options = {
    allowOutsideWorkspace: config.fsAllowOutsideWorkspace === true
  };

  ensureDirectoryWithinRoot(paths.workspaceRoot, paths.agentWorkspaceRoot, options);
  ensureDirectoryWithinRoot(paths.workspaceRoot, paths.skillsRoot, options);
  return paths;
}

export { ensureWorkspaceDirectories, resolveWorkspacePaths };
