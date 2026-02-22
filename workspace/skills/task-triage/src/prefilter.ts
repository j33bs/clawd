export type Tier = "LOCAL" | "REMOTE" | "HUMAN";

export type PrefilterDecision = {
  decision: "PASS" | "DROP" | "ESCALATE";
  tier?: Tier;
  confidence?: number;
  rationale: string;
  flags: string[];
  stats: { task_chars: number; context_chars: number };
};

type PrefilterInput = {
  task: string;
  context: string;
  source?: string;
  rules: any;
};

type SentinelResult = {
  tier_suggestion?: Tier;
  confidence?: number;
  rationale?: string;
  labels?: string[];
};

function toCaseRegex(pattern: string): RegExp | null {
  if (!pattern) return null;
  let body = pattern;
  let flags = "";
  if (body.startsWith("(?i)")) {
    body = body.slice(4);
    flags = "i";
  }
  try {
    return new RegExp(body, flags);
  } catch {
    return null;
  }
}

function matchesRegex(text: string, pattern?: string): boolean {
  if (!pattern) return false;
  const re = toCaseRegex(pattern);
  if (!re) return false;
  return re.test(text);
}

function inList(value: string | undefined, list: string[]): boolean {
  if (!value) return false;
  return list.some((v) => String(v).toLowerCase() === String(value).toLowerCase());
}

function matchesWhen(when: any, input: PrefilterInput, maxTaskChars: number, maxContextChars: number): boolean {
  if (!when || typeof when !== "object") return false;
  if (when.task_regex && !matchesRegex(input.task, String(when.task_regex))) return false;
  if (when.context_regex && !matchesRegex(input.context, String(when.context_regex))) return false;
  if (when.context_too_large === true && input.context.length <= maxContextChars) return false;
  if (when.task_too_large === true && input.task.length <= maxTaskChars) return false;
  return true;
}

export function evaluatePrefilter(input: PrefilterInput): PrefilterDecision {
  const cfg = input.rules?.prefilter || {};
  const enabled = cfg.enabled !== false;
  const maxTaskChars = Number(cfg.max_task_chars ?? 4000);
  const maxContextChars = Number(cfg.max_context_chars ?? 12000);
  const allowlistSources: string[] = Array.isArray(cfg.allowlist_sources) ? cfg.allowlist_sources : [];
  const denylistSources: string[] = Array.isArray(cfg.denylist_sources) ? cfg.denylist_sources : [];

  const stats = { task_chars: input.task.length, context_chars: input.context.length };
  const flags: string[] = [];
  if (stats.task_chars > maxTaskChars) flags.push("TASK_TOO_LARGE");
  if (stats.context_chars > maxContextChars) flags.push("CONTEXT_TOO_LARGE");

  if (!enabled) {
    return { decision: "PASS", rationale: "prefilter disabled", flags, stats };
  }

  if (inList(input.source, denylistSources)) {
    return {
      decision: "ESCALATE",
      tier: "HUMAN",
      confidence: 0.95,
      rationale: "source is denylisted",
      flags: [...flags, "SOURCE_DENYLISTED"],
      stats
    };
  }
  if (allowlistSources.length > 0 && input.source && !inList(input.source, allowlistSources)) {
    return {
      decision: "ESCALATE",
      tier: "REMOTE",
      confidence: 0.85,
      rationale: "source not in allowlist",
      flags: [...flags, "SOURCE_NOT_ALLOWLISTED"],
      stats
    };
  }

  for (const rule of Array.isArray(cfg.drop_if) ? cfg.drop_if : []) {
    if (!matchesWhen(rule?.when, input, maxTaskChars, maxContextChars)) continue;
    return {
      decision: "DROP",
      rationale: String(rule?.rationale || "prefilter drop rule matched"),
      flags,
      stats
    };
  }

  for (const rule of Array.isArray(cfg.escalate_if) ? cfg.escalate_if : []) {
    if (!matchesWhen(rule?.when, input, maxTaskChars, maxContextChars)) continue;
    return {
      decision: "ESCALATE",
      tier: String(rule?.tier || "REMOTE").toUpperCase() as Tier,
      confidence: Number(rule?.confidence ?? 0.8),
      rationale: String(rule?.rationale || "prefilter escalation rule matched"),
      flags,
      stats
    };
  }

  return { decision: "PASS", rationale: "prefilter pass", flags, stats };
}

export function decideFromSentinel(localSentinelResult: SentinelResult | undefined, minConfidence: number): {
  tier: Tier;
  confidence: number;
  rationale: string;
  flags: string[];
} {
  if (!localSentinelResult || typeof localSentinelResult !== "object") {
    return {
      tier: "REMOTE",
      confidence: minConfidence,
      rationale: "low confidence; escalated",
      flags: ["SENTINEL_MISSING"]
    };
  }
  const confidence = Number(localSentinelResult.confidence ?? 0);
  if (confidence >= minConfidence) {
    return {
      tier: (localSentinelResult.tier_suggestion || "REMOTE") as Tier,
      confidence,
      rationale: String(localSentinelResult.rationale || "sentinel classification"),
      flags: Array.isArray(localSentinelResult.labels) ? localSentinelResult.labels : []
    };
  }
  return {
    tier: "REMOTE",
    confidence,
    rationale: "low confidence; escalated",
    flags: ["SENTINEL_LOW_CONFIDENCE"]
  };
}
