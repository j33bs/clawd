"use strict";

function toInt(value, fallback) {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return fallback;
  return Math.floor(n);
}

function clip(text, maxChars) {
  if (text.length <= maxChars) return { value: text, truncated: false };
  return { value: text.slice(0, maxChars), truncated: true };
}

function tokenize(text) {
  const raw = String(text || "").toLowerCase().match(/[a-z0-9]+/g) || [];
  return Array.from(new Set(raw.filter((t) => t.length >= 2)));
}

function buildExcerpt(task, context, rules, sentinelMaxExcerptChars) {
  const pref = (rules && rules.prefilter) || {};
  const maxTask = toInt(pref.max_task_chars, 4000);
  const maxContext = toInt(pref.max_context_chars, 12000);
  const sentinelCap = toInt(sentinelMaxExcerptChars, Number.MAX_SAFE_INTEGER);
  const taskCap = Math.min(maxTask, sentinelCap);
  const contextCap = Math.min(maxContext, sentinelCap);

  const taskClip = clip(String(task || ""), taskCap);
  const contextClip = clip(String(context || ""), contextCap);
  const flags = [];
  if (taskClip.truncated || contextClip.truncated) flags.push("TRUNCATED");
  if (taskClip.truncated) flags.push("TASK_TRUNCATED");
  if (contextClip.truncated) flags.push("CONTEXT_TRUNCATED");

  return {
    task_excerpt: taskClip.value,
    context_excerpt: contextClip.value,
    flags
  };
}

function buildEvidenceBundle(task, context, rules) {
  const cfg = (rules && rules.evidence) || {};
  if (cfg.enabled === false) return undefined;

  const chunkChars = toInt(cfg.chunk_chars, 800);
  const topK = toInt(cfg.top_k, 5);
  const minScore = toInt(cfg.min_score, 1);
  const tokens = tokenize(task);
  if (!context) {
    return { kind: "topk_stub", top_k: topK, selected: [], notes: "no context available" };
  }

  const selected = [];
  const paragraphs = context.split(/\n{2,}/).filter((p) => p.trim().length > 0);
  let cursor = 0;
  let idx = 0;

  const pushChunk = (chunk, start, end) => {
    const lower = chunk.toLowerCase();
    let score = 0;
    for (const t of tokens) {
      if (lower.includes(t)) score += 1;
    }
    if (score >= minScore) {
      selected.push({ id: `chunk-${idx}`, start, end, score });
      idx += 1;
    }
  };

  for (const para of paragraphs) {
    let offset = 0;
    while (offset < para.length) {
      const next = para.slice(offset, offset + chunkChars);
      const start = cursor + offset;
      const end = start + next.length;
      pushChunk(next, start, end);
      offset += chunkChars;
    }
    cursor += para.length + 2;
  }

  selected.sort((a, b) => b.score - a.score || a.start - b.start);
  return {
    kind: "topk_stub",
    top_k: topK,
    selected: selected.slice(0, topK),
    notes: "deterministic token-overlap selector"
  };
}

module.exports = { buildExcerpt, buildEvidenceBundle };
