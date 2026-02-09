'use strict';

const pathAutoresolver = require('./tasks/path_autoresolver');
const dateAwareBriefNamer = require('./tasks/date_aware_brief_namer');
const syntaxLintPrebrief = require('./tasks/syntax_lint_prebrief');
const unifiedLogging = require('./tasks/unified_logging');
const defaultModelProjectionAudit = require('./tasks/default_model_projection_audit');
const markdownLinkNormalizer = require('./tasks/markdown_link_normalizer');
const memoryPromotionAssistant = require('./tasks/memory_promotion_assistant');
const cronTaskSanityCheck = require('./tasks/cron_task_sanity_check');
const templateCacheCleaner = require('./tasks/template_cache_cleaner');
const configHotReloadVerifier = require('./tasks/config_hot_reload_verifier');

const TASKS = {
  path_autoresolver: pathAutoresolver,
  date_aware_brief_namer: dateAwareBriefNamer,
  syntax_lint_prebrief: syntaxLintPrebrief,
  unified_logging: unifiedLogging,
  default_model_projection_audit: defaultModelProjectionAudit,
  markdown_link_normalizer: markdownLinkNormalizer,
  memory_promotion_assistant: memoryPromotionAssistant,
  cron_task_sanity_check: cronTaskSanityCheck,
  template_cache_cleaner: templateCacheCleaner,
  config_hot_reload_verifier: configHotReloadVerifier
};

function listQuickFixes() {
  return Object.keys(TASKS);
}

function runQuickFix(name, context = {}) {
  if (!TASKS[name]) {
    throw new Error(`Unknown quick fix: ${name}`);
  }
  return TASKS[name].run(context);
}

function runAll(context = {}) {
  return listQuickFixes().map((name) => {
    try {
      return {
        name,
        status: 'ok',
        result: runQuickFix(name, context)
      };
    } catch (error) {
      return {
        name,
        status: 'error',
        error: error.message
      };
    }
  });
}

function enqueueMaintenanceTasks(queueStore, options = {}) {
  const intervalSeconds = Number(options.intervalSeconds || 3600);
  const personaPath = options.personaPath ||
    require('node:path').join(process.cwd(), 'sys', 'specialists', 'maintenance_runner', 'persona.json');
  const nowIso = new Date().toISOString();

  return listQuickFixes().map((name) =>
    queueStore.enqueueTask({
      name: `maintenance:${name}`,
      persona_path: personaPath,
      interval_seconds: intervalSeconds,
      next_allowed_time: nowIso,
      enabled: true
    })
  );
}

module.exports = {
  TASKS,
  listQuickFixes,
  runQuickFix,
  runAll,
  enqueueMaintenanceTasks
};
