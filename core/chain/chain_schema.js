function isPlainObject(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function validatePlan(plan) {
  if (!isPlainObject(plan) || !Array.isArray(plan.tasks)) {
    return { ok: false, error: 'plan.tasks missing' };
  }
  if (plan.tasks.length < 1 || plan.tasks.length > 6) {
    return { ok: false, error: 'plan.tasks size out of range' };
  }
  const invalid = plan.tasks.find((task) => !task || !task.id || !task.title || !task.intent);
  if (invalid) {
    return { ok: false, error: 'plan.task missing id/title/intent' };
  }
  return { ok: true };
}

function validateTaskResult(result) {
  if (!isPlainObject(result)) {
    return { ok: false, error: 'task result not object' };
  }
  if (typeof result.text !== 'string') {
    return { ok: false, error: 'task result missing text' };
  }
  return { ok: true };
}

module.exports = {
  validatePlan,
  validateTaskResult
};
