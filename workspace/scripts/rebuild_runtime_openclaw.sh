#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/jeebs/src/clawd"
RUNTIME_DIR="$ROOT/.runtime/openclaw"
RUNTIME_DIST_STAGING_DIR="$ROOT/.runtime/openclaw-dist"
PATCH_FILE="$RUNTIME_DIR/dist/runtime_tool_payload_guard_patch.mjs"
INDEX_FILE="$RUNTIME_DIR/dist/index.js"
NET_FILE="$RUNTIME_DIR/dist/net-COi3RSq7.js"
WS_FILE="$RUNTIME_DIR/dist/ws-CPpn8hzq.js"

echo "repo_sha=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "source=/usr/lib/node_modules/openclaw"
echo "target=$RUNTIME_DIR"

mkdir -p "$RUNTIME_DIR"
# Keep runtime staging artifacts from accumulating hashed files.
rm -rf "$RUNTIME_DIST_STAGING_DIR"
rsync -a --delete /usr/lib/node_modules/openclaw/ "$RUNTIME_DIR/"

if [ -f "$NET_FILE" ] || [ -f "$WS_FILE" ]; then
  node - <<'NODE' "$NET_FILE" "$WS_FILE"
const fs = require('node:fs');
const marker = '/* OPENCLAW_NET_IFACE_FALLBACK */';
const needle = `function pickPrimaryLanIPv4() {\n\tconst nets = os.networkInterfaces();`;
const replacement = `${marker}
let _networkIntrospectionWarned = false;
function safeNetworkInterfaces() {
\ttry {
\t\treturn os.networkInterfaces() ?? {};
\t} catch (error) {
\t\tif (!_networkIntrospectionWarned) {
\t\t\t_networkIntrospectionWarned = true;
\t\t\tconst message = String(error && error.message ? error.message : error || "unknown");
\t\t\tconsole.error(JSON.stringify({
\t\t\t\tevent: "openclaw_network_introspection_unavailable",
\t\t\t\terror: message
\t\t\t}));
\t\t}
\t\treturn {};
\t}
}
function pickPrimaryLanIPv4() {
\tconst nets = safeNetworkInterfaces();`;
for (const file of process.argv.slice(2)) {
  if (!file || !fs.existsSync(file)) continue;
  let src = fs.readFileSync(file, 'utf8');
  if (src.includes(marker)) continue;
  if (!src.includes(needle)) {
    throw new Error(`net helper anchor not found in ${file}`);
  }
  src = src.replace(needle, replacement);
  fs.writeFileSync(file, src);
}
NODE
fi

REPLY_FILE="$(ls "$RUNTIME_DIR"/dist/reply-*.js 2>/dev/null | head -n 1 || true)"
if [ -n "${REPLY_FILE}" ] && [ -f "$REPLY_FILE" ]; then
  node - <<'NODE' "$REPLY_FILE"
const fs = require('node:fs');

const file = process.argv[2];
let src = fs.readFileSync(file, 'utf8');

const execMarker = '/* OPENCLAW_EXEC_PAYLOAD_TRANSPORT */';
if (!src.includes(execMarker)) {
  const execHelperAnchor = 'async function runExecProcess(opts) {';
  const execHelperBlock = `${execMarker}
const OPENCLAW_EXEC_INLINE_MAX_BYTES = 32 * 1024;
let openclawExecPayloadCounter = 0;
function quoteShellArg(value) {
	const s = String(value ?? "");
	return "'" + s.replace(/'/g, "'\\\\''") + "'";
}
function nextExecPayloadCorrelationId() {
	openclawExecPayloadCounter = (openclawExecPayloadCounter + 1) % 1679616;
	return \`exec-\${Date.now().toString(36)}-\${openclawExecPayloadCounter.toString(36).padStart(3, "0")}\`;
}
function externalizeExecCommandIfOversized(command) {
	const raw = String(command ?? "");
	const bytes = Buffer.byteLength(raw, "utf8");
	if (bytes <= OPENCLAW_EXEC_INLINE_MAX_BYTES) return {
		command: raw
	};
	const correlationId = nextExecPayloadCorrelationId();
	try {
		const dir = fs$1.mkdtempSync(path.join(os.tmpdir(), "openclaw-exec-"));
		const scriptPath = path.join(dir, "payload.sh");
		const wrapped = \`#!/usr/bin/env bash\\nset -euo pipefail\\n\${raw}\\n\`;
		fs$1.writeFileSync(scriptPath, wrapped, { encoding: "utf-8", mode: 448 });
		fs$1.chmodSync(scriptPath, 448);
		console.error(JSON.stringify({
			event: "exec_payload_transport",
			mode: "file",
			bytes,
			correlation_id: correlationId
		}));
		return {
			command: \`bash \${quoteShellArg(scriptPath)}\`
		};
	} catch (err) {
		console.error(JSON.stringify({
			event: "exec_payload_transport",
			mode: "inline_fallback",
			bytes,
			correlation_id: correlationId,
			error: String(err)
		}));
		return {
			command: raw
		};
	}
}
`;
  if (!src.includes(execHelperAnchor)) {
    throw new Error('runExecProcess anchor not found');
  }
  src = src.replace(execHelperAnchor, `${execHelperBlock}\n${execHelperAnchor}`);
}

if (!src.includes('const execCommandPrepared = externalizeExecCommandIfOversized')) {
  const execCommandNeedle = 'const execCommand = opts.execCommand ?? opts.command;';
  const execCommandReplacement = `const execCommandPrepared = externalizeExecCommandIfOversized(opts.execCommand ?? opts.command);
\tconst execCommand = execCommandPrepared.command;`;
  if (!src.includes(execCommandNeedle)) {
    throw new Error('execCommand assignment anchor not found');
  }
  src = src.replace(execCommandNeedle, execCommandReplacement);
}

const tgMarker = '/* OPENCLAW_TELEGRAM_ERROR_CORRELATION */';
if (!src.includes(tgMarker)) {
  const tgAnchor = 'const registerTelegramHandlers = ({ cfg, accountId, bot, opts, runtime, mediaMaxBytes, telegramCfg, groupAllowFrom, resolveGroupPolicy, resolveTelegramGroupConfig, shouldSkipUpdate, processMessage, logger }) => {';
const tgBlock = `${tgMarker}
let openclawTelegramErrorCounter = 0;
const OPENCLAW_TELEGRAM_HANDLER_TIMEOUT_MS = (() => {
	const parsed = Number.parseInt(String(process.env.OPENCLAW_TELEGRAM_HANDLER_TIMEOUT_MS || "25000"), 10);
	return Number.isFinite(parsed) && parsed > 0 ? parsed : 25000;
})();
function nextTelegramErrorCorrelationId() {
	openclawTelegramErrorCounter = (openclawTelegramErrorCounter + 1) % 1679616;
	return \`tg-\${Date.now().toString(36)}-\${openclawTelegramErrorCounter.toString(36).padStart(3, "0")}\`;
}
function sleepMs(ms) {
	return new Promise((resolve) => setTimeout(resolve, ms));
}
async function appendTelegramDeadletter(entry) {
	try {
		const deadletterPath = process.env.OPENCLAW_TELEGRAM_DEADLETTER_PATH || path.join(process.cwd(), "workspace", "telemetry", "telegram_deadletter.jsonl");
		await fs$1.mkdir(path.dirname(deadletterPath), { recursive: true });
		await fs$1.appendFile(deadletterPath, JSON.stringify(entry) + "\\n", "utf8");
		return {
			ok: true,
			path: deadletterPath
		};
	} catch (err) {
		console.error(JSON.stringify({
			event: "telegram_deadletter_write_failed",
			error: String(err)
		}));
		return {
			ok: false,
			error: String(err)
		};
	}
}
function extractTelegramEntityUrl(entity) {
	if (!entity || typeof entity !== "object") return "";
	const value = entity.url || entity.text_link || "";
	return typeof value === "string" ? value : "";
}
function isHeavyTelegramUpdateMessage(msg) {
	const text = String(msg?.text ?? msg?.caption ?? "");
	const lowered = text.toLowerCase();
	if (lowered.includes("arxiv.org/abs/") || lowered.includes("arxiv.org/pdf/")) return true;
	if (/https?:\\/\\/\\S+\\.pdf(?:\\b|$)/i.test(text)) return true;
	if (text.length > 1e3) return true;
	const entities = [...Array.isArray(msg?.entities) ? msg.entities : [], ...Array.isArray(msg?.caption_entities) ? msg.caption_entities : []];
	if (entities.some((entity) => {
		const url = extractTelegramEntityUrl(entity).toLowerCase();
		return url.includes("arxiv.org/abs/") || url.includes("arxiv.org/pdf/") || /\\.pdf(?:\\b|$)/i.test(url);
	})) return true;
	if (msg?.document || msg?.video || msg?.audio || msg?.voice || msg?.video_note || msg?.animation) return true;
	return false;
}
async function handleTelegramProcessingError({ bot, event, runtime, err }) {
	const correlationId = nextTelegramErrorCorrelationId();
	const stage = String(err?.stage || err?.code || "handler");
	const errorText = String(err && err.message ? err.message : err);
	console.error(JSON.stringify({
		event: "telegram_handler_failed",
		correlation_id: correlationId,
		update_id: event.msg?.message_id ?? null,
		stage,
		err_class: err?.name || "Error",
		err_message: errorText
	}));
	await appendTelegramDeadletter({
		ts: new Date().toISOString(),
		correlation_id: correlationId,
		update_id: event.msg?.message_id ?? null,
		route: "telegram_inbound",
		chat_id_hash: event.chatId != null ? String(event.chatId).slice(-6) : null,
		stage,
		err: errorText
	});
	runtime.error?.(danger(event.errorMessage + " (correlation_id=" + correlationId + ", stage=" + stage + "): " + errorText));
	try {
		await sendTelegramErrorReplyWithRetry({
			bot,
			event,
			runtime,
			correlationId,
			messageText: "Error (code: " + correlationId + "). Gateway logs contain details."
		});
	} catch (notifyErr) {
		runtime.error?.(danger("telegram error notification failed (correlation_id=" + correlationId + "): " + String(notifyErr)));
	}
}
function isRetryableTelegramSendError(err) {
	const status = Number(err?.error_code ?? err?.statusCode ?? err?.status ?? 0);
	if (status === 429 || status >= 500) return true;
	const text = String(err?.description || err?.message || err || "");
	return /timeout|timed out|network request|fetch failed|ecconn|econn|socket hang up|temporar/i.test(text);
}
async function sendTelegramErrorReplyWithRetry({ bot, event, runtime, correlationId, messageText }) {
	const delays = [250, 1000, 3000];
	let lastErr;
	for (let attempt = 1; attempt <= delays.length; attempt += 1) {
		try {
			await withTelegramApiErrorLogging({
				operation: "sendMessage",
				runtime,
				fn: () => bot.api.sendMessage(event.chatId, messageText, buildTypingThreadParams(event.messageThreadId))
			});
			return;
		} catch (err) {
			lastErr = err;
			const retryable = isRetryableTelegramSendError(err);
			console.error(JSON.stringify({
				event: "telegram_send_retry",
				correlation_id: correlationId,
				attempt,
				retryable,
				error: String(err)
			}));
			if (!retryable || attempt >= delays.length) break;
			await sleepMs(delays[attempt - 1]);
		}
	}
	throw lastErr || new Error("telegram sendMessage failed");
}
async function runTelegramInboundWithTimeout(fn, event, runtime) {
	let timer = null;
	try {
		await Promise.race([
			fn(),
			new Promise((_, reject) => {
				timer = setTimeout(() => {
					const timeoutErr = new Error(\`telegram handler timed out after \${OPENCLAW_TELEGRAM_HANDLER_TIMEOUT_MS}ms\`);
					timeoutErr.code = "TELEGRAM_HANDLER_TIMEOUT";
					timeoutErr.stage = "pipeline";
					reject(timeoutErr);
				}, OPENCLAW_TELEGRAM_HANDLER_TIMEOUT_MS);
			})
		]);
	} finally {
		if (timer) clearTimeout(timer);
		runtime.log?.(warn(\`telegram_handler_finally chatId=\${event.chatId} messageId=\${event.msg?.message_id ?? "n/a"}\`));
	}
}
`;
  if (!src.includes(tgAnchor)) {
    throw new Error('registerTelegramHandlers anchor not found');
  }
  src = src.replace(tgAnchor, `${tgBlock}\n${tgAnchor}`);
}

const handleAnchor = 'const handleInboundMessageLike = async (event) => {';
const handleEndAnchor = '\n\tbot.on("message", async (ctx) => {';
const handleStart = src.indexOf(handleAnchor);
if (handleStart !== -1) {
  const handleEnd = src.indexOf(handleEndAnchor, handleStart);
  if (handleEnd !== -1) {
    let section = src.slice(handleStart, handleEnd);
    section = section.replace(
      /await processInboundMessage\(\{([\s\S]*?)\}\);/,
      'const inboundPayload = {$1};\n\t\t\tif (isHeavyTelegramUpdateMessage(event.msg)) {\n\t\t\t\tconst startedAt = Date.now();\n\t\t\t\tconst lane = `telegram-heavy:${String(event.chatId)}`;\n\t\t\t\tenqueueCommandInLane(lane, async () => {\n\t\t\t\t\tawait processInboundMessage(inboundPayload);\n\t\t\t\t}).catch(async (queueErr) => {\n\t\t\t\t\tawait handleTelegramProcessingError({\n\t\t\t\t\t\tbot,\n\t\t\t\t\t\tevent,\n\t\t\t\t\t\truntime,\n\t\t\t\t\t\terr: queueErr\n\t\t\t\t\t});\n\t\t\t\t});\n\t\t\t\tconsole.error(JSON.stringify({\n\t\t\t\t\tevent: "telegram_handler_deferred",\n\t\t\t\t\tupdate_id: event.msg?.message_id ?? null,\n\t\t\t\t\tchat_id_hash: event.chatId != null ? String(event.chatId).slice(-6) : null,\n\t\t\t\t\tlane,\n\t\t\t\t\telapsed_ms: Date.now() - startedAt\n\t\t\t\t}));\n\t\t\t\treturn;\n\t\t\t}\n\t\t\tawait runTelegramInboundWithTimeout(() => processInboundMessage(inboundPayload), event, runtime);'
    );
    section = section.replace(
      /\t\t\} catch \(err\) \{[\s\S]*?\t\t\}\n\t\};/,
      '\t\t} catch (err) {\n\t\t\tawait handleTelegramProcessingError({\n\t\t\t\tbot,\n\t\t\t\tevent,\n\t\t\t\truntime,\n\t\t\t\terr\n\t\t\t});\n\t\t}\n\t};'
    );
    src = src.slice(0, handleStart) + section + src.slice(handleEnd);
  }
}

fs.writeFileSync(file, src);
NODE
fi

PI_AI_PROVIDER_FILE="$RUNTIME_DIR/node_modules/@mariozechner/pi-ai/dist/providers/openai-completions.js"
if [ -f "$PI_AI_PROVIDER_FILE" ]; then
  node - <<'NODE' "$PI_AI_PROVIDER_FILE"
const fs = require('node:fs');
const path = process.argv[2];
let src = fs.readFileSync(path, 'utf8');

const marker = '/* OPENCLAW_LOCAL_VLLM_TOOLCALL_GATE */';
if (!src.includes(marker)) {
  const helperAnchor = 'function hasToolHistory(messages) {';
  const helperBlock = `${marker}
function isLocalVllmTarget(baseUrl) {
    const value = String(baseUrl || "").trim().toLowerCase();
    if (!value)
        return false;
    if (value.includes("127.0.0.1:8001") || value.includes("localhost:8001") || value.includes("[::1]:8001"))
        return true;
    return value.includes("/vllm") || value.includes("vllm");
}
function isLocalVllmToolCallEnabled() {
    const value = String(process.env.OPENCLAW_VLLM_TOOLCALL || "0").trim().toLowerCase();
    return value === "1" || value === "true" || value === "yes" || value === "on";
}
function applyLocalVllmToolPayloadGate(baseUrl, params) {
    if (!isLocalVllmTarget(baseUrl))
        return;
    if (isLocalVllmToolCallEnabled())
        return;
    delete params.tools;
    delete params.tool_choice;
}
function vllmTokenGuardEnabled() {
    const value = String(process.env.OPENCLAW_VLLM_TOKEN_GUARD || "0").trim().toLowerCase();
    return value === "1" || value === "true" || value === "yes" || value === "on";
}
function parsePositiveInt(value, fallback) {
    const parsed = Number.parseInt(String(value ?? fallback), 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}
function estimatePromptTokens(messages) {
    if (!Array.isArray(messages))
        return 0;
    let chars = 0;
    for (const msg of messages) {
        if (!msg || typeof msg !== "object")
            continue;
        const roleLen = typeof msg.role === "string" ? msg.role.length : 0;
        let contentLen = 0;
        const content = msg.content;
        if (typeof content === "string") {
            contentLen = content.length;
        } else if (Array.isArray(content)) {
            for (const part of content) {
                if (!part || typeof part !== "object")
                    continue;
                if (typeof part.text === "string")
                    contentLen += part.text.length;
                if (typeof part.input_text === "string")
                    contentLen += part.input_text.length;
            }
        } else if (content && typeof content === "object") {
            if (typeof content.text === "string")
                contentLen += content.text.length;
            if (typeof content.input_text === "string")
                contentLen += content.input_text.length;
        }
        chars += roleLen + contentLen + 16;
    }
    return Math.ceil((chars / 4) * 1.2);
}
function truncateMessagesToBudget(messages, contextMax, completionTokens) {
    if (!Array.isArray(messages))
        return { messages: [], promptEstimate: 0 };
    const system = [];
    const other = [];
    for (const msg of messages) {
        if (msg && typeof msg === "object" && String(msg.role || "").toLowerCase() === "system")
            system.push(msg);
        else
            other.push(msg);
    }
    for (let i = other.length - 1; i >= 0; i -= 1) {
        const candidate = [...system, ...other.slice(i)];
        const est = estimatePromptTokens(candidate);
        if (est + completionTokens <= contextMax)
            return { messages: candidate, promptEstimate: est };
    }
    return { messages: system, promptEstimate: estimatePromptTokens(system) };
}
function logVllmTokenGuard(event) {
    try {
        console.warn(JSON.stringify(event));
    } catch {
        // ignore logging failures
    }
}
function applyLocalVllmTokenGuard(baseUrl, params) {
    if (!isLocalVllmTarget(baseUrl))
        return;
    if (!vllmTokenGuardEnabled())
        return;
    const contextMax = parsePositiveInt(process.env.OPENCLAW_VLLM_CONTEXT_MAX_TOKENS, 8192);
    const modeRaw = String(process.env.OPENCLAW_VLLM_TOKEN_GUARD_MODE || "reject").trim().toLowerCase();
    const mode = modeRaw === "truncate" ? "truncate" : "reject";
    const requestedCompletion = parsePositiveInt(params.max_completion_tokens, 512);
    const maxAllowedCompletion = Math.max(1, contextMax - 256);
    const clampedCompletion = Math.min(requestedCompletion, maxAllowedCompletion);
    let modified = clampedCompletion !== params.max_completion_tokens;
    params.max_completion_tokens = clampedCompletion;
    const promptEstimate = estimatePromptTokens(params.messages);
    if (promptEstimate + clampedCompletion <= contextMax) {
        if (modified) {
            logVllmTokenGuard({
                subsystem: "tool_payload_trace",
                event: "vllm_token_guard_preflight",
                action: "clamp",
                callsite_tag: "pi-ai.openai-completions.pre_dispatch",
                context_max: contextMax,
                prompt_est: promptEstimate,
                max_completion_tokens: clampedCompletion
            });
        }
        return;
    }
    if (mode === "truncate") {
        const originalCount = Array.isArray(params.messages) ? params.messages.length : 0;
        const truncated = truncateMessagesToBudget(params.messages, contextMax, clampedCompletion);
        params.messages = truncated.messages;
        modified = modified || (Array.isArray(params.messages) && params.messages.length < originalCount);
        if (truncated.promptEstimate + clampedCompletion <= contextMax) {
            logVllmTokenGuard({
                subsystem: "tool_payload_trace",
                event: "vllm_token_guard_preflight",
                action: "truncate",
                callsite_tag: "pi-ai.openai-completions.pre_dispatch",
                context_max: contextMax,
                prompt_est: truncated.promptEstimate,
                max_completion_tokens: clampedCompletion,
                message_count_after: Array.isArray(params.messages) ? params.messages.length : 0
            });
            return;
        }
    }
    logVllmTokenGuard({
        subsystem: "tool_payload_trace",
        event: "vllm_token_guard_preflight",
        action: "reject",
        callsite_tag: "pi-ai.openai-completions.pre_dispatch",
        context_max: contextMax,
        prompt_est: promptEstimate,
        requested_max_completion_tokens: clampedCompletion
    });
    const err = new Error("Local vLLM request exceeds context budget");
    err.code = "VLLM_CONTEXT_BUDGET_EXCEEDED";
    err.prompt_est = promptEstimate;
    err.context_max = contextMax;
    err.requested_max_completion_tokens = clampedCompletion;
    throw err;
}
`;
  if (!src.includes(helperAnchor)) {
    throw new Error('openai-completions helper anchor not found');
  }
  src = src.replace(helperAnchor, `${helperBlock}\n${helperAnchor}`);

  const applyAnchor = '    // OpenRouter provider routing preferences';
  const applyBlock = '    applyLocalVllmToolPayloadGate(model.baseUrl, params);\n    applyLocalVllmTokenGuard(model.baseUrl, params);\n';
  if (!src.includes(applyAnchor)) {
    throw new Error('openai-completions apply anchor not found');
  }
  src = src.replace(applyAnchor, `${applyBlock}${applyAnchor}`);

  fs.writeFileSync(path, src);
}
NODE
fi

cat > "$PATCH_FILE" <<'JS'
// Runtime overlay from repo branch to enforce tool payload invariant.
// Marker: OPENCLAW_STRICT_TOOL_PAYLOAD
// Marker: gateway.edge.final_dispatch
// Marker: payload sanitizer bypassed

import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const http = require("node:http");
const https = require("node:https");

const STRICT = String(process.env.OPENCLAW_STRICT_TOOL_PAYLOAD || "").trim().toLowerCase();
const strictEnabled = STRICT === "1" || STRICT === "true" || STRICT === "yes" || STRICT === "on";
const TRACE_VLLM = String(process.env.OPENCLAW_TRACE_VLLM_OUTBOUND || "").trim().toLowerCase();
const traceVllmEnabled = TRACE_VLLM === "1" || TRACE_VLLM === "true" || TRACE_VLLM === "yes" || TRACE_VLLM === "on";
const CALLSITE = "gateway.edge.final_dispatch";
const VLLM_LOCAL_PORTS = new Set(["8000", "8001"]);
let requestCounter = 0;

function nextRequestId() {
  requestCounter = (requestCounter + 1) % 1679616;
  return `${Date.now().toString(36)}-${requestCounter.toString(36).padStart(3, "0")}`;
}

function redactUrl(rawUrl) {
  if (!rawUrl) return "";
  try {
    const parsed = new URL(String(rawUrl));
    parsed.search = "";
    return parsed.toString();
  } catch {
    return String(rawUrl).replace(/\?.*$/, "");
  }
}

function stackFingerprint() {
  const stack = String(new Error().stack || "")
    .split("\n")
    .slice(1)
    .map((line) => line.trim())
    .filter((line) => line && !line.includes("node:internal") && !line.includes("runtime_tool_payload_guard_patch.mjs"))
    .slice(0, 5);
  return stack.join(" | ");
}

function parseJsonBody(body) {
  if (typeof body !== "string") return null;
  const trimmed = body.trim();
  if (!trimmed.startsWith("{") || !trimmed.endsWith("}")) return null;
  try {
    return JSON.parse(trimmed);
  } catch {
    return null;
  }
}

function detectBodyFlags(bodyText) {
  const text = typeof bodyText === "string" ? bodyText : "";
  const parsed = parseJsonBody(text);
  const topKeys = parsed && typeof parsed === "object" && !Array.isArray(parsed) ? Object.keys(parsed) : [];
  return {
    payload_size_bytes: Buffer.byteLength(text, "utf8"),
    payload_top_keys: topKeys,
    body_has_tools: text.includes('"tools"'),
    body_has_tool_choice: text.includes('"tool_choice"'),
    body_has_tool_calls: text.includes('"tool_calls"'),
    body_has_function_call: text.includes('"function_call"')
  };
}

function shortSnippet(value, maxLen = 160) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > maxLen ? `${text.slice(0, maxLen)}...` : text;
}

function isVllmTarget(urlString, host, port) {
  const hostLc = String(host || "").toLowerCase();
  const urlLc = String(urlString || "").toLowerCase();
  const localHost = hostLc === "127.0.0.1" || hostLc === "localhost" || hostLc === "::1";
  if (hostLc.includes("vllm") || urlLc.includes("vllm")) return true;
  if (localHost && VLLM_LOCAL_PORTS.has(String(port || "")) && urlLc.includes("/chat/completions")) return true;
  if ((urlLc.includes("127.0.0.1:8001") || urlLc.includes("localhost:8001")) && urlLc.includes("/chat/completions")) return true;
  return false;
}

function logVllmTrace(event, fields) {
  if (!traceVllmEnabled) return;
  const line = {
    subsystem: "tool_payload_trace",
    event,
    ts: new Date().toISOString(),
    callsite_tag: CALLSITE,
    stack_fingerprint: stackFingerprint()
  };
  Object.assign(line, fields || {});
  // eslint-disable-next-line no-console
  console.log(JSON.stringify(line));
}

function sanitizePayloadObject(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return { changed: false, value };
  const payload = { ...value };
  const hadTools = Object.prototype.hasOwnProperty.call(payload, "tools");
  const hadToolChoice = Object.prototype.hasOwnProperty.call(payload, "tool_choice");
  const hasValidTools = Array.isArray(payload.tools) && payload.tools.length > 0;
  if (!hasValidTools) {
    if (hadTools) delete payload.tools;
    if (hadToolChoice) delete payload.tool_choice;
  }
  const changed = JSON.stringify(payload) !== JSON.stringify(value);
  return { changed, value: payload };
}

function sanitizeBodyMaybeJson(body) {
  if (typeof body !== "string") return { changed: false, body };
  const trimmed = body.trim();
  if (!trimmed.startsWith("{") || !trimmed.endsWith("}")) return { changed: false, body };
  try {
    const parsed = JSON.parse(body);
    const out = sanitizePayloadObject(parsed);
    return out.changed ? { changed: true, body: JSON.stringify(out.value) } : { changed: false, body };
  } catch {
    return { changed: false, body };
  }
}

function logSanitized() {
  const line = JSON.stringify({
    subsystem: "tool_payload",
    event: strictEnabled ? "TOOL_PAYLOAD_SANITIZER_BYPASSED" : "tool_payload_sanitized_after_invalid_shape",
    callsite_tag: CALLSITE,
    message: "payload sanitizer bypassed; stripped invalid tool_choice/tools shape"
  });
  // eslint-disable-next-line no-console
  console.error(line);
}

const originalFetch = globalThis.fetch;
if (typeof originalFetch === "function") {
  globalThis.fetch = async function patchedFetch(input, init) {
    const nextInit = init ? { ...init } : init;
    const targetUrl = typeof input === "string" ? input : input?.url;
    const method = nextInit?.method || input?.method || "GET";
    const urlHost = (() => {
      try {
        return new URL(String(targetUrl)).hostname;
      } catch {
        return "";
      }
    })();
    const urlPort = (() => {
      try {
        const u = new URL(String(targetUrl));
        return u.port || (u.protocol === "https:" ? "443" : "80");
      } catch {
        return "";
      }
    })();
    const isVllm = isVllmTarget(targetUrl, urlHost, urlPort);
    let requestId = null;
    let wireBody = "";

    if (nextInit && typeof nextInit.body === "string") {
      const out = sanitizeBodyMaybeJson(nextInit.body);
      if (out.changed) {
        nextInit.body = out.body;
        logSanitized();
      }
      wireBody = nextInit.body;
      if (isVllm) {
        requestId = nextRequestId();
        logVllmTrace("vllm_outbound_trace_send", {
          request_id: requestId,
          target_url: redactUrl(targetUrl),
          method: String(method || "GET").toUpperCase(),
          content_length: Buffer.byteLength(wireBody, "utf8"),
          ...detectBodyFlags(wireBody)
        });
      }
    }
    if (input && typeof input === "object" && "url" in input && typeof input.clone === "function") {
      try {
        const req = input;
        const contentType = req.headers?.get?.("content-type") || "";
        if (!init && contentType.includes("application/json")) {
          const clone = req.clone();
          const text = await clone.text();
          const out = sanitizeBodyMaybeJson(text);
          const traceBody = out.changed ? out.body : text;
          wireBody = traceBody;
          if (isVllm) {
            requestId = nextRequestId();
            logVllmTrace("vllm_outbound_trace_send", {
              request_id: requestId,
              target_url: redactUrl(req.url),
              method: String(method || req.method || "GET").toUpperCase(),
              content_length: Buffer.byteLength(traceBody, "utf8"),
              ...detectBodyFlags(traceBody)
            });
          }
          if (out.changed) {
            const headers = new Headers(req.headers || {});
            const patched = new Request(req.url, {
              method: req.method,
              headers,
              body: out.body,
              redirect: req.redirect,
              signal: req.signal
            });
            logSanitized();
            const response = await originalFetch.call(this, patched);
            if (isVllm) {
              let errSnippet = "";
              if (response.status >= 400) {
                try {
                  errSnippet = shortSnippet(await response.clone().text());
                } catch {
                  errSnippet = "";
                }
              }
              logVllmTrace("vllm_outbound_trace_resp", {
                request_id: requestId || nextRequestId(),
                target_url: redactUrl(req.url),
                method: String(method || req.method || "GET").toUpperCase(),
                status_code: Number(response.status || 0),
                err_snippet: errSnippet
              });
            }
            return response;
          }
        }
      } catch {
        // Preserve original request flow on patch failure.
      }
    }
    const response = await originalFetch.call(this, input, nextInit);
    if (isVllm) {
      let errSnippet = "";
      if (response.status >= 400) {
        try {
          errSnippet = shortSnippet(await response.clone().text());
        } catch {
          errSnippet = "";
        }
      }
      logVllmTrace("vllm_outbound_trace_resp", {
        request_id: requestId || nextRequestId(),
        target_url: redactUrl(targetUrl),
        method: String(method || "GET").toUpperCase(),
        status_code: Number(response.status || 0),
        err_snippet: errSnippet
      });
    }
    return response;
  };
}

function isChatCompletionsTarget(args) {
  try {
    const first = args[0];
    const maybeOptions = args.length > 1 && typeof args[1] === "object" ? args[1] : null;
    const method = String(maybeOptions?.method || first?.method || "GET").toUpperCase();
    if (method !== "POST") return false;
    if (typeof first === "string") return first.includes("/chat/completions");
    if (first && typeof first === "object") {
      const path = String(first.path || first.pathname || "");
      const href = String(first.href || "");
      return path.includes("/chat/completions") || href.includes("/chat/completions");
    }
  } catch {
    // Fall through.
  }
  return false;
}

function patchNodeRequest(mod) {
  try {
    const original = mod.request;
    if (typeof original !== "function") return;
    mod.request = function patchedRequest(...args) {
    const req = original.apply(this, args);
    const first = args[0];
    const second = args.length > 1 && typeof args[1] === "object" ? args[1] : null;
    const host = second?.hostname || second?.host || first?.hostname || first?.host || "";
    const port = second?.port || first?.port || "";
    const path = second?.path || first?.path || first?.pathname || "";
    const protocol = first?.protocol || (mod === https ? "https:" : "http:");
    const method = String(second?.method || first?.method || "GET").toUpperCase();
    const targetUrl = typeof first === "string"
      ? first
      : `${protocol}//${host}${port ? `:${port}` : ""}${path || ""}`;
    const candidate = isChatCompletionsTarget(args) || isVllmTarget(targetUrl, host, port);
    if (!candidate) return req;

    const origWrite = req.write.bind(req);
    const origEnd = req.end.bind(req);
    const chunks = [];

    req.write = function patchedWrite(chunk, encoding, cb) {
      if (chunk !== undefined && chunk !== null) {
        chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(String(chunk), typeof encoding === "string" ? encoding : "utf8"));
      }
      if (typeof cb === "function") cb();
      return true;
    };

    req.end = function patchedEnd(chunk, encoding, cb) {
      if (chunk !== undefined && chunk !== null) {
        chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(String(chunk), typeof encoding === "string" ? encoding : "utf8"));
      }
      const body = Buffer.concat(chunks).toString("utf8");
      const out = sanitizeBodyMaybeJson(body);
      const finalBody = out.changed ? out.body : body;
      const isVllm = isVllmTarget(targetUrl, host, port);
      const requestId = isVllm ? nextRequestId() : null;
      if (isVllm) {
        logVllmTrace("vllm_outbound_trace_send", {
          request_id: requestId,
          target_url: redactUrl(targetUrl),
          method: String(method || "POST").toUpperCase(),
          content_length: Buffer.byteLength(finalBody, "utf8"),
          ...detectBodyFlags(finalBody)
        });
        req.once("response", (res) => {
          const statusCode = Number(res?.statusCode || 0);
          if (statusCode < 400) {
            logVllmTrace("vllm_outbound_trace_resp", {
              request_id: requestId,
              target_url: redactUrl(targetUrl),
              method: String(method || "POST").toUpperCase(),
              status_code: statusCode
            });
            return;
          }
          const chunks = [];
          let received = 0;
          res.on("data", (buf) => {
            if (!buf) return;
            const chunkBuf = Buffer.isBuffer(buf) ? buf : Buffer.from(String(buf));
            if (received < 512) {
              const remaining = 512 - received;
              chunks.push(chunkBuf.subarray(0, remaining));
            }
            received += chunkBuf.length;
          });
          res.on("end", () => {
            const snippet = shortSnippet(Buffer.concat(chunks).toString("utf8"));
            logVllmTrace("vllm_outbound_trace_resp", {
              request_id: requestId,
              target_url: redactUrl(targetUrl),
              method: String(method || "POST").toUpperCase(),
              status_code: statusCode,
              err_snippet: snippet
            });
          });
        });
      }
      if (out.changed) {
        try {
          req.setHeader("content-length", Buffer.byteLength(finalBody, "utf8"));
        } catch {
          // Ignore header adjustment failures.
        }
        logSanitized();
      }
      return origEnd(finalBody, "utf8", cb);
    };

    // Preserve access to the real writer for code paths expecting immediate flush.
    req._openclawOrigWrite = origWrite;
    return req;
    };
  } catch {
    // Some runtimes expose read-only request handles; fail open for trace mode.
  }
}

patchNodeRequest(http);
patchNodeRequest(https);
JS

if ! head -n 8 "$INDEX_FILE" | rg -q 'runtime_tool_payload_guard_patch\.mjs'; then
  tmp="$(mktemp)"
  if head -n 1 "$INDEX_FILE" | rg -q '^#!'; then
    {
      head -n 1 "$INDEX_FILE"
      echo 'import "./runtime_tool_payload_guard_patch.mjs";'
      tail -n +2 "$INDEX_FILE"
    } > "$tmp"
  else
    {
      echo 'import "./runtime_tool_payload_guard_patch.mjs";'
      cat "$INDEX_FILE"
    } > "$tmp"
  fi
  mv "$tmp" "$INDEX_FILE"
fi

echo "marker_check_runtime_dist:"
rg -n -S "OPENCLAW_STRICT_TOOL_PAYLOAD|gateway\\.edge\\.final_dispatch|payload sanitizer bypassed" "$RUNTIME_DIR/dist" || true
