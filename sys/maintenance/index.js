'use strict';

const QUICK_FIX_NAMES = [
  'path_autoresolver',
  'date_aware_brief_namer',
  'syntax_lint_prebrief',
  'unified_logging',
  'default_model_projection_audit',
  'markdown_link_normalizer',
  'memory_promotion_assistant',
  'cron_task_sanity_check',
  'template_cache_cleaner',
  'config_hot_reload_verifier'
];

function listQuickFixes() {
  return QUICK_FIX_NAMES.slice();
}

module.exports = {
  QUICK_FIX_NAMES,
  listQuickFixes
};
