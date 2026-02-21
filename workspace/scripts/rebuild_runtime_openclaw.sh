#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/jeebs/src/clawd"
RUNTIME_DIR="$ROOT/.runtime/openclaw"
PATCH_FILE="$RUNTIME_DIR/dist/runtime_tool_payload_guard_patch.mjs"
INDEX_FILE="$RUNTIME_DIR/dist/index.js"

echo "repo_sha=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "source=/usr/lib/node_modules/openclaw"
echo "target=$RUNTIME_DIR"

mkdir -p "$RUNTIME_DIR"
rsync -a --delete /usr/lib/node_modules/openclaw/ "$RUNTIME_DIR/"

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

function isVllmTarget(urlString, host, port) {
  const hostLc = String(host || "").toLowerCase();
  const urlLc = String(urlString || "").toLowerCase();
  const localHost = hostLc === "127.0.0.1" || hostLc === "localhost" || hostLc === "::1";
  if (hostLc.includes("vllm") || urlLc.includes("vllm")) return true;
  if (localHost && VLLM_LOCAL_PORTS.has(String(port || "")) && urlLc.includes("/chat/completions")) return true;
  if ((urlLc.includes("127.0.0.1:8001") || urlLc.includes("localhost:8001")) && urlLc.includes("/chat/completions")) return true;
  return false;
}

function logVllmTrace({ targetUrl, method, contentLength, parsedPayload, callsiteTag }) {
  if (!traceVllmEnabled) return;
  const payloadKeys = parsedPayload && typeof parsedPayload === "object" && !Array.isArray(parsedPayload)
    ? Object.keys(parsedPayload)
    : [];
  const line = JSON.stringify({
    subsystem: "tool_payload_trace",
    event: "vllm_outbound_trace",
    ts: new Date().toISOString(),
    target_url: redactUrl(targetUrl),
    method: String(method || "GET").toUpperCase(),
    content_length: Number(contentLength || 0),
    payload_top_keys: payloadKeys,
    has_tools: payloadKeys.includes("tools"),
    has_tool_choice: payloadKeys.includes("tool_choice"),
    callsite_tag: callsiteTag || CALLSITE,
    stack_fingerprint: stackFingerprint()
  });
  // eslint-disable-next-line no-console
  console.log(line);
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

    if (nextInit && typeof nextInit.body === "string") {
      const out = sanitizeBodyMaybeJson(nextInit.body);
      if (out.changed) {
        nextInit.body = out.body;
        logSanitized();
      }
      if (isVllmTarget(targetUrl, urlHost, urlPort)) {
        const parsed = parseJsonBody(nextInit.body);
        logVllmTrace({
          targetUrl,
          method,
          contentLength: Buffer.byteLength(nextInit.body, "utf8"),
          parsedPayload: parsed,
          callsiteTag: CALLSITE
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
          if (isVllmTarget(req.url, urlHost, urlPort)) {
            const parsed = parseJsonBody(traceBody);
            logVllmTrace({
              targetUrl: req.url,
              method,
              contentLength: Buffer.byteLength(traceBody, "utf8"),
              parsedPayload: parsed,
              callsiteTag: CALLSITE
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
            return originalFetch.call(this, patched);
          }
        }
      } catch {
        // Preserve original request flow on patch failure.
      }
    }
    return originalFetch.call(this, input, nextInit);
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
      if (isVllmTarget(targetUrl, host, port)) {
        const parsed = parseJsonBody(finalBody);
        logVllmTrace({
          targetUrl,
          method,
          contentLength: Buffer.byteLength(finalBody, "utf8"),
          parsedPayload: parsed,
          callsiteTag: CALLSITE
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
