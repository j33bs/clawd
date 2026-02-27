# Machine-surface compliance check

timestamp_utc: 20260227T102258Z
branch: main
head: edcd2a9

artifacts:
- /tmp/health_headers_20260227T102258Z.txt
- /tmp/api_miss_headers_20260227T102258Z.txt
- /tmp/api_procs_headers_20260227T102258Z.txt
- /tmp/assert_machine_surface_20260227T102258Z.txt
- /tmp/api_html_hits_20260227T102258Z.txt
- /tmp/assert_fail_hits_20260227T102258Z.txt

pass_fail:
- HTML_FAIL: 0
- ASSERT_FAIL: 1
- decision: HARDENED

notes:
- Header probes showed Content-Type: text/html for /health and /api/* at runtime.
- Hardening applied in scripts/system2_http_edge.js for strict /api prefix handling in policy and OPTIONS preflight.
- Added deterministic regression test: tests/no_html_on_api_routes.test.js.

tests:
- node --check scripts/system2_http_edge.js: PASS
- node --test tests/no_html_on_api_routes.test.js: PASS
- node --test tests/no_html_on_machine_routes.test.js: PASS
