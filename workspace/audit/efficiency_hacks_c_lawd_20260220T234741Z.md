# Efficiency hacks for C_Lawd

- UTC: 20260220T234741Z
- Baseline SHA: e8ad6d7
- Branch: codex/perf/efficiency-hacks-20260221
- Node: v25.6.0
- npm: 11.8.0
- Python: Python 3.14.3

## Baseline status
```
?? workspace/audit/efficiency_hacks_c_lawd_20260220T234741Z.md
```

## Timings
### Baseline microbench
```text
H2_store_put_200_sec=0.050167
H9_econ_append_1000_sec=0.055354
H10_router_init_200_sec=0.019576
H4_quote_runs20_sec=1.186305
```

### Phase 1 timings
```text
H2_store_put_200_sec=0.024434
H9_econ_append_1000_sec=0.037890
H10_router_init_200_sec=0.017526
```

### Phase 1 targeted tests
```text
python3 -m unittest -q tests_unittest.test_econ_log tests.test_hivemind_store_efficiency tests.test_ingest_memory tests.test_ingest_handoffs tests.test_query_scope tests_unittest.test_policy_router_policy_cache
PASS
```

### Phase 2/3 timings
```text
H1_search_200_queries_sec=0.912667
H7_volatility_1000_calls_sec=0.016145
H8_trails_add_500_same_text_sec=0.022912
H8_trails_embed_compute_count=1
H4_quote_runs20_sec=1.040941
H6_analyze_workers2_sec=0.335865
```

## Files touched
- `core_infra/econ_log.py`
- `core_infra/volatility_metrics.py`
- `workspace/hivemind/hivemind/store.py`
- `workspace/hivemind/hivemind/intelligence/utils.py`
- `workspace/hivemind/hivemind/intelligence/suggestions.py`
- `workspace/hivemind/hivemind/intelligence/pruning.py`
- `workspace/hivemind/hivemind/intelligence/summaries.py`
- `workspace/hivemind/hivemind/intelligence/contradictions.py`
- `workspace/hivemind/hivemind/cli.py`
- `workspace/hivemind/hivemind/trails.py`
- `workspace/scripts/policy_router.py`
- `scripts/get_daily_quote.js`
- `scripts/analyze_session_patterns.js`
- tests: `tests_unittest/test_econ_log.py`, `tests/test_hivemind_store_efficiency.py`, `tests_unittest/test_policy_router_policy_cache.py`, `tests/test_intelligence_units_cache.py`, `tests/get_daily_quote_manifest.test.js`, `tests/analyze_session_patterns.test.js`, `tests_unittest/test_volatility_metrics.py`, `tests_unittest/test_hivemind_trails.py`

## Hack-by-hack implementation notes
1. HiveMind search + access N+1 IO:
- `HiveMindStore.search()` now records access in append-only `access_log.jsonl`.
- `HiveMindStore.all_units()` overlays rolling access counts from access log in-memory; no full KB rewrite on each search.

2. Hash index rewrite on each `put()`:
- hash index lazy-loaded once per store instance.
- flush batched (`HASH_FLUSH_EVERY=50`) and on `close()`/`atexit`.
- atomic write via temp file + `os.replace`.

3. Multiple `all_units()` reads in maintenance:
- added `get_all_units_cached(store, ttl_seconds=60)` in `intelligence/utils.py`.
- `suggestions`, `pruning`, `summaries` now accept optional `units` and use cached loader by default.
- `cli scan-contradictions` now sources units via shared cache.

4. Daily quote triple disk read:
- `scripts/get_daily_quote.js` now uses `quotes_manifest.json` (mtime/size fingerprint).
- runtime picks from manifest and reads only selected byte slice.
- supports `--rebuild` and deterministic `--seed` for test harness.

5. Repeated tokenization in search scoring:
- token list generated at ingest (`record["tokens"]`).
- search reuses stored tokens; legacy rows fallback to compute-once path without behavior change.

6. Session pattern analysis full sync scan:
- switched to streaming line scanner (`scanFileStreamSync`) to avoid full-file loads.
- added worker-thread parallel scan path (`analyzeSessionsConcurrent`, `--workers`).
- output ordering kept deterministic.

7. Volatility recompute from scratch:
- added bounded LRU memoization for ATR and rolling vol (`lru_cache`).
- added `cache_stats()` and `clear_cache()` for deterministic test assertions.

8. Trails embedding hash recomputation:
- added bounded LRU embed cache (`maxsize=1024`) in `trails.py`.
- repeated same text/tags reuse cached vector.

9. `fsync()` per event in econ log:
- `append_jsonl()` now batches fsync by threshold/time (`50` events or `0.5s`).
- preserves append order and immediate line write; `flush_pending()` and `atexit` enforce final durability.

10. `policy_router` root/policy reload overhead:
- `_resolve_repo_root()` now memoized.
- `load_policy()` now mtime-keyed cached with lock; reload occurs only on file mtime change.

## Cache contracts (bounds/TTL/invalidation)
- HiveMind hash index cache: batch flush every 50 puts, flush on close/atexit, atomic replace.
- HiveMind units cache: TTL default 60s (`HIVEMIND_UNITS_CACHE_TTL_SECONDS`) + mtime invalidation.
- Intelligence shared cache: 60s TTL, weak-keyed cache per store.
- Volatility memo cache: ATR max 256 keys, rolling vol max 512 keys.
- Trails embed cache: max 1024 keys.
- Policy cache: one entry per policy path + mtime, lock-protected.

## Before/after timing deltas
- Hack #2 (`store.put` 200 units): `0.050167s -> 0.024434s`.
- Hack #9 (`econ_log` 1000 appends): `0.055354s -> 0.037890s`.
- Hack #10 (`PolicyRouter()` x200): `0.019576s -> 0.017526s`.
- Hack #4 (`get_daily_quote` x20): `1.186305s -> 1.040941s`.

## Commands run (targeted)
```text
python3 -m unittest -q tests_unittest.test_econ_log tests.test_hivemind_store_efficiency tests.test_ingest_memory tests.test_ingest_handoffs tests.test_query_scope tests_unittest.test_policy_router_policy_cache
python3 -m unittest -q tests.test_intelligence_suggestions tests.test_intelligence_pruning tests.test_intelligence_summaries tests.test_intelligence_contradictions tests.test_intelligence_units_cache tests.test_query_scope tests.test_hivemind_store_efficiency
python3 -m unittest -q tests_unittest.test_volatility_metrics tests_unittest.test_hivemind_trails tests.test_intelligence_suggestions tests.test_intelligence_pruning tests.test_intelligence_summaries tests.test_intelligence_units_cache
python3 -m unittest -q tests_unittest.test_econ_log tests.test_hivemind_store_efficiency tests.test_intelligence_suggestions tests.test_intelligence_pruning tests.test_intelligence_summaries tests.test_intelligence_contradictions tests.test_intelligence_units_cache tests.test_ingest_memory tests.test_ingest_handoffs tests.test_query_scope tests_unittest.test_volatility_metrics tests_unittest.test_hivemind_trails tests_unittest.test_policy_router_policy_cache
node tests/analyze_session_patterns.test.js
node tests/get_daily_quote_manifest.test.js
```

## Full gate result
```text
python3 -m unittest -q  -> FAIL (pre-existing origin/main baseline: failures=5, errors=8 in policy_router/teamchat compatibility suites)
npm test --silent       -> FAILURES: 1/39 (propagates same python baseline failure)
```

## Baseline parity evidence (origin/main)
- main worktree: `/Users/heathyeager/clawd/.worktrees/efficiency_baseline_main`
- command outputs:
  - `python3 -m unittest -q` on `origin/main`: `FAILED (failures=5, errors=8)` with same failing suites (`test_policy_router_tacti_main_flow`, `test_policy_router_teamchat_intent`, `test_router_proprioception`).
  - `npm test --silent` on `origin/main`: `FAILURES: 1/38` (same propagated python baseline failure).
- conclusion: this branch does not introduce the full-gate red status; failures are pre-existing on baseline.
