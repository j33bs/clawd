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

import * as http from "node:http";
import * as https from "node:https";

const STRICT = String(process.env.OPENCLAW_STRICT_TOOL_PAYLOAD || "").trim().toLowerCase();
const strictEnabled = STRICT === "1" || STRICT === "true" || STRICT === "yes" || STRICT === "on";
const CALLSITE = "gateway.edge.final_dispatch";

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
    if (nextInit && typeof nextInit.body === "string") {
      const out = sanitizeBodyMaybeJson(nextInit.body);
      if (out.changed) {
        nextInit.body = out.body;
        logSanitized();
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
  const original = mod.request;
  if (typeof original !== "function") return;
  mod.request = function patchedRequest(...args) {
    const req = original.apply(this, args);
    if (!isChatCompletionsTarget(args)) return req;

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
