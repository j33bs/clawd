# Open Questions & TACTI Investigation
timestamp_utc: 20260227T112140Z
host: Heath-MacBook
user: heathyeager

## OPEN_QUESTIONS.md surface
-rw-r--r--@ 1 heathyeager  staff  311191 Feb 27 19:41 workspace/governance/OPEN_QUESTIONS.md
mode=-rw-r--r-- uid=501 gid=20 size=311191 bytes mtime=Feb 27 19:41:34 2026
  311191 workspace/governance/OPEN_QUESTIONS.md

## Cron context (best effort)

## Wanderer references to OPEN_QUESTIONS + locking

## Size + additive mirror decision
  311191 workspace/governance/OPEN_QUESTIONS.md
Decision: add OPEN_QUESTIONS_INDEX.md and dual-write mirror shards; no historical migration.

## TACTI naming scan
workspace/research/TOPICS.md:1:# TACTI(C)-R Foundational Research Topics
workspace/research/TOPICS.md:4:**TACTI(C)-R**: Temporality, Arousal, Cross-Timescale, Collapse, Repairable
workspace/research/TOPICS.md:6:Repository naming note: this doc keeps `TACTI(C)-R` as the canonical label; `TACTI` is shorthand when discussing a single lens.
workspace/research/TACTI_framework_integration.md:1:# TACTI(C)-R Framework Integration: Agent Architecture Research
workspace/research/TACTI_framework_integration.md:9:This document is my attempt to synthesize everything I've learned about agent architectures today and map it to the TACTI(C)-R framework that Heath and I have been developing. It's not just a literature review — it's a trail of thoughts, moments of insight, and implementation ideas that emerged from diving deep into the research.
workspace/research/TACTI_framework_integration.md:164:         │     TACTI(C)-R LAYER                       │

## Link/reference scan (best effort)
workspace/research/TOPICS.md:63:python3 research_ingest.py add --url "https://..." --topic cross_timescale
workspace/research/TACTI_framework_integration.md:103:│    (memory/YYYY-MM-DD.md)           │

## Housekeeping: ports
NO_LISTENER_8181
NO_LISTENER_18990

## launchd list (filtered)
52:-	0	ai.openclaw.env-bootstrap
132:-	0	com.apple.security.KeychainStasher
149:-	0	com.apple.SiriTTSTrainingAgent
193:-	0	com.apple.speech.speechdatainstallerd
237:-	0	com.apple.security.cloudkeychainproxy3
283:674	0	com.apple.containermanagerd
301:85632	0	ai.openclaw.gateway
378:-	0	com.apple.ContainerMigrationService
440:83721	-9	com.apple.keychainsharingmessagingd
444:-	0	com.apple.security.XPCKeychainSandboxCheck
463:83673	-9	com.apple.security.keychain-circle-notification

## recent openclaw logs (tail only, redacted)
total 83512
drwxr-xr-x   7 heathyeager  staff       224 Feb 16 12:51 .
drwx------@ 46 heathyeager  staff      1472 Feb 27 14:39 ..
-rw-------@  1 heathyeager  staff     11493 Feb 26 13:02 config-audit.jsonl
-rw-r--r--   1 heathyeager  staff  40696018 Feb 27 21:04 gateway.err.log
-rw-r--r--   1 heathyeager  staff   1010859 Feb 27 21:07 gateway.log
-rw-r--r--@  1 heathyeager  staff    189150 Feb  9 15:09 prompt_audit_gateway.jsonl
-rw-r--r--@  1 heathyeager  staff     13100 Feb 15 18:01 vllm.log
OPENCLAW_EDGE_PORT=18789 OPENCLAW_EDGE_UPSTREAM_PORT=18790
node:internal/modules/cjs/loader:1456
  throw err;
  ^

Error: Cannot find module '/Users/heathyeager/scripts/system2_http_edge.js'
    at Module._resolveFilename (node:internal/modules/cjs/loader:1453:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1064:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1069:22)
    at Module._load (node:internal/modules/cjs/loader:1239:25)
    at wrapModuleLoad (node:internal/modules/cjs/loader:255:19)
    at Module.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:154:5)
    at node:internal/main/run_main_module:33:47 {
  code: 'MODULE_NOT_FOUND',
  requireStack: []
}

Node.js v25.6.0
/Users/heathyeager/clawd/scripts/run_openclaw_gateway_repo.sh:4: BASH_SOURCE[0]: parameter not set
OPENCLAW_REPO_RUNTIME=system2_http_edge
OPENCLAW_REPO_ROOT=/Users/heathyeager
OPENCLAW_REPO_SHA=unknown
OPENCLAW_REPO_BRANCH=unknown
OPENCLAW_ENTRYPOINT=/Users/heathyeager/scripts/system2_http_edge.js
OPENCLAW_BUILD repo_sha=unknown branch=unknown entrypoint=/Users/heathyeager/scripts/system2_http_edge.js
OPENCLAW_UPSTREAM_ENTRY=/Users/heathyeager/.npm-global/lib/node_modules/openclaw/dist/entry.js
OPENCLAW_EDGE_PORT=18789 OPENCLAW_EDGE_UPSTREAM_PORT=18790
node:internal/modules/cjs/loader:1456
  throw err;
  ^

Error: Cannot find module '/Users/heathyeager/scripts/system2_http_edge.js'
    at Module._resolveFilename (node:internal/modules/cjs/loader:1453:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1064:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1069:22)
    at Module._load (node:internal/modules/cjs/loader:1239:25)
    at wrapModuleLoad (node:internal/modules/cjs/loader:255:19)
    at Module.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:154:5)
    at node:internal/main/run_main_module:33:47 {
  code: 'MODULE_NOT_FOUND',
  requireStack: []
}

Node.js v25.6.0
/Users/heathyeager/clawd/scripts/run_openclaw_gateway_repo.sh:4: BASH_SOURCE[0]: parameter not set
OPENCLAW_REPO_RUNTIME=system2_http_edge
OPENCLAW_REPO_ROOT=/Users/heathyeager
OPENCLAW_REPO_SHA=unknown
OPENCLAW_REPO_BRANCH=unknown
OPENCLAW_ENTRYPOINT=/Users/heathyeager/scripts/system2_http_edge.js
OPENCLAW_BUILD repo_sha=unknown branch=unknown entrypoint=/Users/heathyeager/scripts/system2_http_edge.js
OPENCLAW_UPSTREAM_ENTRY=/Users/heathyeager/.npm-global/lib/node_modules/openclaw/dist/entry.js
OPENCLAW_EDGE_PORT=18789 OPENCLAW_EDGE_UPSTREAM_PORT=18790
node:internal/modules/cjs/loader:1456
  throw err;
  ^

Error: Cannot find module '/Users/heathyeager/scripts/system2_http_edge.js'
    at Module._resolveFilename (node:internal/modules/cjs/loader:1453:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1064:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1069:22)
    at Module._load (node:internal/modules/cjs/loader:1239:25)
    at wrapModuleLoad (node:internal/modules/cjs/loader:255:19)
    at Module.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:154:5)
    at node:internal/main/run_main_module:33:47 {
  code: 'MODULE_NOT_FOUND',
  requireStack: []
}

Node.js v25.6.0
/Users/heathyeager/clawd/scripts/run_openclaw_gateway_repo.sh:4: BASH_SOURCE[0]: parameter not set
OPENCLAW_REPO_RUNTIME=openclaw_gateway
OPENCLAW_REPO_ROOT=/Users/heathyeager
OPENCLAW_REPO_SHA=unknown
OPENCLAW_REPO_BRANCH=unknown
OPENCLAW_ENTRYPOINT=openclaw gateway start
OPENCLAW_BUILD repo_sha=unknown branch=unknown entrypoint=openclaw gateway start
OPENCLAW_GATEWAY_BIND=loopback OPENCLAW_GATEWAY_PORT=18789
OPENCLAW_REPO_RUNTIME=openclaw_gateway
OPENCLAW_REPO_ROOT=/Users/heathyeager/clawd
OPENCLAW_REPO_SHA=f25c42e
OPENCLAW_REPO_BRANCH=codex/fix/launchd-gateway-subcommand-20260227
OPENCLAW_ENTRYPOINT=openclaw gateway run
OPENCLAW_BUILD repo_sha=f25c42e branch=codex/fix/launchd-gateway-subcommand-20260227 entrypoint=openclaw gateway run
OPENCLAW_GATEWAY_BIND=loopback OPENCLAW_GATEWAY_PORT=18789
2026-02-27T09:28:10.226Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/Users/heathyeager/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
OPENCLAW_REPO_RUNTIME=openclaw_gateway
OPENCLAW_REPO_ROOT=/Users/heathyeager/clawd
OPENCLAW_REPO_SHA=05faeb3
OPENCLAW_REPO_BRANCH=codex/fix/launchd-gateway-subcommand-20260227
OPENCLAW_ENTRYPOINT=openclaw gateway run
OPENCLAW_BUILD repo_sha=05faeb3 branch=codex/fix/launchd-gateway-subcommand-20260227 entrypoint=openclaw gateway run
OPENCLAW_GATEWAY_BIND=loopback OPENCLAW_GATEWAY_PORT=18789
2026-02-27T09:41:58.909Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/Users/heathyeager/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
OPENCLAW_REPO_RUNTIME=openclaw_gateway
OPENCLAW_REPO_ROOT=/Users/heathyeager/clawd
OPENCLAW_REPO_SHA=05faeb3
OPENCLAW_REPO_BRANCH=codex/fix/launchd-gateway-subcommand-20260227
OPENCLAW_ENTRYPOINT=openclaw gateway run
OPENCLAW_BUILD repo_sha=05faeb3 branch=codex/fix/launchd-gateway-subcommand-20260227 entrypoint=openclaw gateway run
OPENCLAW_GATEWAY_BIND=loopback OPENCLAW_GATEWAY_PORT=18789
2026-02-27T09:43:17.134Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/Users/heathyeager/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
OPENCLAW_REPO_RUNTIME=openclaw_gateway
OPENCLAW_REPO_ROOT=/Users/heathyeager/clawd
OPENCLAW_REPO_SHA=e6a062a
OPENCLAW_REPO_BRANCH=main
OPENCLAW_ENTRYPOINT=openclaw gateway run
OPENCLAW_BUILD repo_sha=e6a062a branch=main entrypoint=openclaw gateway run
OPENCLAW_GATEWAY_BIND=loopback OPENCLAW_GATEWAY_PORT=18789
2026-02-27T09:44:35.706Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/Users/heathyeager/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
2026-02-27T09:44:42.001Z [telegram] deleteMyCommands failed: Network request for 'deleteMyCommands' failed!
OPENCLAW_REPO_RUNTIME=openclaw_gateway
OPENCLAW_REPO_ROOT=/Users/heathyeager/clawd
OPENCLAW_REPO_SHA=edcd2a9
OPENCLAW_REPO_BRANCH=main
OPENCLAW_ENTRYPOINT=openclaw gateway run
OPENCLAW_BUILD repo_sha=edcd2a9 branch=main entrypoint=openclaw gateway run
OPENCLAW_GATEWAY_BIND=loopback OPENCLAW_GATEWAY_PORT=18789
2026-02-27T10:23:01.551Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/Users/heathyeager/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
2026-02-27T21:04:26.680+10:00 [tools] edit failed: Missing required parameter: oldText (oldText or old_string). Supply correct parameters before retrying.

## Targeted checks
- python3 -m py_compile workspace/research/research_wanderer.py: PASS
- python3 workspace/research/research_wanderer.py append-test /tmp/open_questions_append_test_20260227T112140Z.md:
APPEND_TEST_OK target=/tmp/open_questions_append_test_20260227T112140Z.md

## PR55 Tighten Pass (20260227T113838Z)
- rebase_origin_main: up_to_date (no conflicts)
- lock_behavior: non-blocking lock with timeout 5s and explicit OPEN_QUESTIONS_LOCK_TIMEOUT stderr line
- dedupe_behavior: hash includes normalized question + source topic; duplicate suppression is time-windowed
- retention_bound: dedupe timestamps pruned by QUESTION_STATE_TTL_DAYS

### Commands
- python3 -m py_compile workspace/research/research_wanderer.py
- python3 workspace/research/research_wanderer.py append-test /tmp/oq_append_test_20260227T113838Z.md
APPEND_TEST_OK target=/tmp/oq_append_test_20260227T113838Z.md
- python3 workspace/research/research_wanderer_selftest.py
PASS research_wanderer self-test

