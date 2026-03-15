const DEFAULT_SOURCE_UI_TASKS_URL =
  typeof process.env.OPENCLAW_SOURCE_UI_TASKS_URL === 'string' &&
  process.env.OPENCLAW_SOURCE_UI_TASKS_URL.trim()
    ? process.env.OPENCLAW_SOURCE_UI_TASKS_URL.trim()
    : 'http://100.113.160.1:18990/api/tasks';

const SOURCE_UI_TASK_TAG_RE = /<source-ui-task>\s*([\s\S]*?)\s*<\/source-ui-task>/i;
const SOURCE_UI_RECEIPT_RE = /^Source UI receipt:\s*#\S+/im;
const UNVERIFIED_QUEUE_CLAIM_RE =
  /(?:queued:|queued in source ui|added to (?:the )?(?:source ui )?backlog|backlog live|queue live|visible\.\s*flowing\.|synced\.\s*flowing\.)/i;

const QUEUE_FAILURE_TEXT =
  "I drafted the Source UI task, but I couldn't confirm it in the live backlog yet.";

function cleanVisibleText(text) {
  return String(text || '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function hasSourceUiReceipt(text) {
  return SOURCE_UI_RECEIPT_RE.test(String(text || ''));
}

function extractSourceUiTaskDirective(text) {
  const source = String(text || '');
  const match = SOURCE_UI_TASK_TAG_RE.exec(source);
  if (!match) return null;

  const visibleText = cleanVisibleText(source.replace(match[0], ''));
  let parsed;
  try {
    parsed = JSON.parse(match[1]);
  } catch (error) {
    return {
      visibleText,
      error: new Error(`Invalid source-ui-task JSON: ${error.message}`)
    };
  }

  const title = typeof parsed?.title === 'string' ? parsed.title.trim() : '';
  if (!title) {
    return {
      visibleText,
      error: new Error('source-ui-task directive requires a non-empty title')
    };
  }

  const task = {
    title,
    description: typeof parsed.description === 'string' ? parsed.description.trim() : undefined,
    priority: typeof parsed.priority === 'string' ? parsed.priority.trim() : 'medium',
    project: typeof parsed.project === 'string' ? parsed.project.trim() : 'source-ui',
    assignee: typeof parsed.assignee === 'string' ? parsed.assignee.trim() : '',
    created_by: typeof parsed.created_by === 'string' ? parsed.created_by.trim() : 'telegram-main',
    status: 'backlog'
  };

  if (typeof parsed.notes === 'string' && parsed.notes.trim()) task.notes = parsed.notes.trim();

  return { visibleText, task, error: null };
}

function formatSourceUiReceipt(task) {
  const id = task?.id ?? '?';
  const title = typeof task?.title === 'string' ? task.title.trim() : 'Untitled task';
  const status = typeof task?.status === 'string' && task.status.trim() ? task.status.trim() : 'backlog';
  return `Source UI receipt: #${id} ${title} (${status})`;
}

async function readJsonResponse(response) {
  const raw = await response.text();
  if (!raw.trim()) return {};
  return JSON.parse(raw);
}

async function queueSourceUiTask({ task, fetchImpl = globalThis.fetch, tasksUrl = DEFAULT_SOURCE_UI_TASKS_URL }) {
  if (typeof fetchImpl !== 'function') {
    throw new Error('fetch is unavailable for Source UI task queueing');
  }

  const response = await fetchImpl(tasksUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(task)
  });

  const data = await readJsonResponse(response);
  if (!response.ok) {
    throw new Error(
      `Source UI queue failed (${response.status}): ${typeof data?.error === 'string' ? data.error : response.statusText}`
    );
  }
  if (data?.id == null || typeof data?.title !== 'string') {
    throw new Error('Source UI queue response missing task receipt fields');
  }
  return data;
}

function downgradeUnverifiedQueueClaim(text) {
  const source = cleanVisibleText(text);
  if (!source) return source;
  if (hasSourceUiReceipt(source)) return source;
  if (!UNVERIFIED_QUEUE_CLAIM_RE.test(source)) return source;
  return QUEUE_FAILURE_TEXT;
}

async function applySourceUiTaskDirectiveToText({
  text,
  fetchImpl = globalThis.fetch,
  tasksUrl = DEFAULT_SOURCE_UI_TASKS_URL
} = {}) {
  const source = String(text || '');
  const directive = extractSourceUiTaskDirective(source);
  if (!directive) {
    const downgraded = downgradeUnverifiedQueueClaim(source);
    return {
      text: downgraded,
      changed: downgraded !== source,
      queued: false,
      receipt: null,
      error: null
    };
  }

  if (directive.error) {
    return {
      text: QUEUE_FAILURE_TEXT,
      changed: true,
      queued: false,
      receipt: null,
      error: directive.error
    };
  }

  try {
    const receipt = await queueSourceUiTask({
      task: directive.task,
      fetchImpl,
      tasksUrl
    });
    const baseText = cleanVisibleText(directive.visibleText);
    const receiptLine = formatSourceUiReceipt(receipt);
    const nextText = baseText ? `${baseText}\n\n${receiptLine}` : receiptLine;
    return {
      text: nextText,
      changed: nextText !== source,
      queued: true,
      receipt,
      error: null
    };
  } catch (error) {
    return {
      text: QUEUE_FAILURE_TEXT,
      changed: true,
      queued: false,
      receipt: null,
      error
    };
  }
}

export {
  DEFAULT_SOURCE_UI_TASKS_URL,
  QUEUE_FAILURE_TEXT,
  SOURCE_UI_TASK_TAG_RE,
  UNVERIFIED_QUEUE_CLAIM_RE,
  applySourceUiTaskDirectiveToText,
  downgradeUnverifiedQueueClaim,
  extractSourceUiTaskDirective,
  formatSourceUiReceipt,
  hasSourceUiReceipt,
  queueSourceUiTask
};
