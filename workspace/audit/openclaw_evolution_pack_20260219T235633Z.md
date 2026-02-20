# OpenClaw Evolution Pack

- UTC: 20260219T235633Z
- Branch: codex/feat/openclaw-evolution-pack-20260220

## Phase 0 Baseline

Note: branch uses codex/ prefix per workspace branch policy.

```text
$ git status --porcelain -uall
 M workspace/state/tacti_cr/events.jsonl

$ git rev-parse --short HEAD
834dfe0

$ git branch --show-current
codex/fix/audit-policy-router-tests-20260220

$ node -v
v25.6.0

$ npm -v
11.8.0

$ python3 -V
Python 3.14.3
```

## Phase 1 Discovery

```text
$ rg -n "dream_consolidation|temporal\.py|reservoir\.py|trails\.py|peer_graph\.py|active_inference|semantic_immune|arousal_oscillator|valence" -S .
./README.md:27:- **`peer_graph.py`** — Murmuration-style sparse peer connections (each agent tracks ~7 neighbors)
./README.md:29:- **`reservoir.py`** — Echo-state reservoir computing for temporal pattern processing
./README.md:30:- **`trails.py`** — External memory with decay and reinforcement (like slime trails)
./workspace/CODEX_Source_UI_TACTI_Upgrade.md:28:| **Dream Consolidation** | `workspace/tacti_cr/dream_consolidation.py` | Memory consolidation status, last run |
./workspace/CODEX_Source_UI_TACTI_Upgrade.md:30:| **Semantic Immune** | `workspace/tacti_cr/semantic_immune.py` | Quarantine stats, recent blocks |
./workspace/CODEX_Source_UI_TACTI_Upgrade.md:31:| **Arousal Oscillator** | `workspace/tacti_cr/arousal_oscillator.py` | Current energy level, hourly histogram |
./workspace/CODEX_Source_UI_TACTI_Upgrade.md:32:| **Trail Memory** | `workspace/hivemind/hivemind/trails.py` | Memory heatmap, recent trails |
./workspace/CODEX_Source_UI_TACTI_Upgrade.md:33:| **HiveMind Peer Graph** | `workspace/hivemind/hivemind/peer_graph.py` | Agent connections visualization |
./workspace/CODEX_Source_UI_TACTI_Upgrade.md:115:- Backend API exists: `workspace/source-ui/api/trails.py`
./workspace/AUDIT_AIF_PHASE1_20260219.md:10:  - `workspace/tacti_cr/active_inference_agent.py`
./workspace/AUDIT_AIF_PHASE1_20260219.md:29:  - `python3 -m py_compile workspace/tacti_cr/external_memory.py workspace/tacti_cr/efe_calculator.py workspace/tacti_cr/curiosity.py workspace/tacti_cr/active_inference_agent.py workspace/scripts/external_memory_demo.py` (pass)
./workspace/policy/expression_manifest.json:11:      "feature_name": "dream_consolidation",
./workspace/policy/expression_manifest.json:17:      "feature_name": "semantic_immune",
./workspace/policy/expression_manifest.json:24:      "activation_conditions": {"valence_min": -0.2},
./tests_unittest/test_hivemind_active_inference.py:13:from hivemind.active_inference import PreferenceModel  # noqa: E402
./tests_unittest/test_tacti_cr_novel_10.py:20:from tacti_cr.arousal_oscillator import ArousalOscillator
./tests_unittest/test_tacti_cr_novel_10.py:21:from tacti_cr.dream_consolidation import run_consolidation
./tests_unittest/test_tacti_cr_novel_10.py:25:from tacti_cr.semantic_immune import assess_content, approve_quarantine
./tests_unittest/test_tacti_cr_novel_10.py:27:from tacti_cr.valence import current_valence, routing_bias, update_valence
./tests_unittest/test_tacti_cr_novel_10.py:44:    def test_arousal_oscillator_bins_and_explain(self):
./tests_unittest/test_tacti_cr_novel_10.py:67:                json.dumps({"features": [{"feature_name": "prefetch", "activation_conditions": {"valence_min": -0.1}, "suppression_conditions": {}, "priority": 1}]}, indent=2),
./tests_unittest/test_tacti_cr_novel_10.py:73:                {"valence": 0.2, "budget_remaining": 0.9, "local_available": True},
./tests_unittest/test_tacti_cr_novel_10.py:94:    def test_dream_consolidation_stable(self):
./tests_unittest/test_tacti_cr_novel_10.py:105:            os.environ["TACTI_CR_DREAM_CONSOLIDATION"] = "1"
./tests_unittest/test_tacti_cr_novel_10.py:113:    def test_semantic_immune_quarantine_and_approve(self):
./tests_unittest/test_tacti_cr_novel_10.py:116:            os.environ["TACTI_CR_SEMANTIC_IMMUNE"] = "1"
./tests_unittest/test_tacti_cr_novel_10.py:136:    def test_mirror_and_valence_local_state(self):
./tests_unittest/test_tacti_cr_novel_10.py:140:            os.environ["TACTI_CR_VALENCE"] = "1"
./tests_unittest/test_tacti_cr_novel_10.py:144:            update_valence("coder", {"failed": True, "retry_loops": 2}, repo_root=root)
./tests_unittest/test_tacti_cr_novel_10.py:145:            val = current_valence("coder", repo_root=root)
./workspace/CODEX_TASK_LIST.md:58:**File:** `workspace/tacti_cr/active_inference_agent.py`
./workspace/tacti_cr/valence.py:1:"""Affective valence engine with half-life decay and routing bias signals."""
./workspace/tacti_cr/valence.py:16:    return root / "workspace" / "state" / "valence" / f"{agent}.json"
./workspace/tacti_cr/valence.py:29:        return {"valence": 0.0, "updated_at": _now().isoformat()}
./workspace/tacti_cr/valence.py:36:    return {"valence": 0.0, "updated_at": _now().isoformat()}
./workspace/tacti_cr/valence.py:44:def current_valence(agent: str, *, repo_root: Path | None = None, now: datetime | None = None) -> float:
./workspace/tacti_cr/valence.py:45:    if not is_enabled("valence"):
./workspace/tacti_cr/valence.py:52:    half_life = get_float("valence_half_life_hours", 6.0, clamp=(0.5, 48.0))
./workspace/tacti_cr/valence.py:53:    decayed = float(data.get("valence", 0.0)) * math.exp(-math.log(2.0) * age_hours / half_life)
./workspace/tacti_cr/valence.py:57:def update_valence(agent: str, outcome: dict[str, Any], *, repo_root: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
./workspace/tacti_cr/valence.py:58:    if not is_enabled("valence"):
./workspace/tacti_cr/valence.py:59:        return {"ok": False, "reason": "valence_disabled", "valence": 0.0}
./workspace/tacti_cr/valence.py:61:    value = current_valence(agent, repo_root=repo_root, now=dt_now)
./workspace/tacti_cr/valence.py:72:    payload = {"agent": agent, "valence": value, "updated_at": dt_now.isoformat().replace("+00:00", "Z")}
./workspace/tacti_cr/valence.py:74:    return {"ok": True, "valence": value}
./workspace/tacti_cr/valence.py:78:    value = current_valence(agent, repo_root=repo_root)
./workspace/tacti_cr/valence.py:80:        "valence": value,
./workspace/tacti_cr/valence.py:87:__all__ = ["current_valence", "update_valence", "routing_bias"]
./tests_unittest/test_policy_router_active_inference_hook.py:19:    def test_active_inference_predict_and_update_in_execute(self):
./tests_unittest/test_policy_router_active_inference_hook.py:25:            ai_state = tmp / "active_inference_state.json"
./tests_unittest/test_policy_router_active_inference_hook.py:33:                "ENABLE_ACTIVE_INFERENCE": "1",
./tests_unittest/test_policy_router_active_inference_hook.py:37:                with patch.object(policy_router, "ACTIVE_INFERENCE_STATE_PATH", ai_state):
./tests_unittest/test_policy_router_active_inference_hook.py:55:            self.assertIn("active_inference", captured["context_metadata"])
./tests_unittest/test_policy_router_active_inference_hook.py:56:            ai = captured["context_metadata"]["active_inference"]
./workspace/tacti_cr/semantic_immune.py:43:    base = repo_root / "workspace" / "state" / "semantic_immune"
./workspace/tacti_cr/semantic_immune.py:90:    if not is_enabled("semantic_immune"):
./workspace/tacti_cr/semantic_immune.py:91:        return {"ok": True, "reason": "semantic_immune_disabled", "quarantined": False}
./workspace/state/tacti_cr/events.jsonl:1:{"ts": 1771506277399, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
./workspace/state/tacti_cr/events.jsonl:2:{"ts": 1771506277399, "event": "tacti_cr.valence_bias", "detail": {"intent": "coding", "agent_id": "main", "bias": {"valence": 0.0, "prefer_local": false, "tighten_budget": false, "exploration_bias": false}}}
./workspace/state/tacti_cr/events.jsonl:4:{"ts": 1771535085092, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
./workspace/state/tacti_cr/events.jsonl:5:{"ts": 1771535085092, "event": "tacti_cr.valence_bias", "detail": {"intent": "coding", "agent_id": "main", "bias": {"valence": 0.0, "prefer_local": false, "tighten_budget": false, "exploration_bias": false}}}
./workspace/state/tacti_cr/events.jsonl:7:{"ts": 1771535094165, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
./workspace/state/tacti_cr/events.jsonl:8:{"ts": 1771535094165, "event": "tacti_cr.valence_bias", "detail": {"intent": "coding", "agent_id": "main", "bias": {"valence": 0.0, "prefer_local": false, "tighten_budget": false, "exploration_bias": false}}}
./workspace/state/tacti_cr/events.jsonl:10:{"ts": 1771535104622, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
./workspace/state/tacti_cr/events.jsonl:11:{"ts": 1771535104622, "event": "tacti_cr.valence_bias", "detail": {"intent": "coding", "agent_id": "main", "bias": {"valence": 0.0, "prefer_local": false, "tighten_budget": false, "exploration_bias": false}}}
./workspace/state/tacti_cr/events.jsonl:13:{"ts": 1771535114296, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
./workspace/state/tacti_cr/events.jsonl:14:{"ts": 1771535114296, "event": "tacti_cr.valence_bias", "detail": {"intent": "coding", "agent_id": "main", "bias": {"valence": 0.0, "prefer_local": false, "tighten_budget": false, "exploration_bias": false}}}
./workspace/state/tacti_cr/events.jsonl:16:{"ts": 1771535122066, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
./workspace/state/tacti_cr/events.jsonl:17:{"ts": 1771535122066, "event": "tacti_cr.valence_bias", "detail": {"intent": "coding", "agent_id": "main", "bias": {"valence": 0.0, "prefer_local": false, "tighten_budget": false, "exploration_bias": false}}}
./workspace/state/tacti_cr/events.jsonl:19:{"ts": 1771535125674, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
./workspace/state/tacti_cr/events.jsonl:20:{"ts": 1771535125674, "event": "tacti_cr.valence_bias", "detail": {"intent": "coding", "agent_id": "main", "bias": {"valence": 0.0, "prefer_local": false, "tighten_budget": false, "exploration_bias": false}}}
./workspace/state/tacti_cr/events.jsonl:22:{"ts": 1771535797828, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
./workspace/state/tacti_cr/events.jsonl:23:{"ts": 1771535797828, "event": "tacti_cr.valence_bias", "detail": {"intent": "coding", "agent_id": "main", "bias": {"valence": 0.0, "prefer_local": false, "tighten_budget": false, "exploration_bias": false}}}
./workspace/state/tacti_cr/events.jsonl:25:{"ts": 1771543883143, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
./workspace/state/tacti_cr/events.jsonl:26:{"ts": 1771543883144, "event": "tacti_cr.valence_bias", "detail": {"intent": "coding", "agent_id": "main", "bias": {"valence": 0.0, "prefer_local": false, "tighten_budget": false, "exploration_bias": false}}}
./workspace/state/tacti_cr/events.jsonl:28:{"ts": 1771543886658, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
./workspace/state/tacti_cr/events.jsonl:29:{"ts": 1771543886658, "event": "tacti_cr.valence_bias", "detail": {"intent": "coding", "agent_id": "main", "bias": {"valence": 0.0, "prefer_local": false, "tighten_budget": false, "exploration_bias": false}}}
./workspace/state/tacti_cr/events.jsonl:31:{"ts": 1771543900227, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
./workspace/state/tacti_cr/events.jsonl:32:{"ts": 1771543900227, "event": "tacti_cr.valence_bias", "detail": {"intent": "coding", "agent_id": "main", "bias": {"valence": 0.0, "prefer_local": false, "tighten_budget": false, "exploration_bias": false}}}
./workspace/state/tacti_cr/events.jsonl:34:{"ts": 1771543903469, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}

$ rg -n "router_(route_selected|attempt|skip|success|escalate|fail)|log_event\(|EVENT_LOG|execute_with_escalation" workspace/scripts core scripts
scripts/itc_classify.py:44:EVENT_LOG = BASE_DIR / "itc" / "classify_events.jsonl"
scripts/itc_classify.py:82:def log_event(event_type, detail=None):
scripts/itc_classify.py:84:    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
scripts/itc_classify.py:92:        with open(EVENT_LOG, "a", encoding="utf-8") as f:
scripts/itc_classify.py:156:    result = router.execute_with_escalation(
scripts/itc_classify.py:225:    log_event("classify_start", {
scripts/itc_classify.py:270:                    log_event("llm_router_fail", {"reason_code": llm_backend})
scripts/itc_classify.py:293:    log_event("classify_done", {
scripts/memory_tool.py:69:    store.log_event("query", agent=args.agent, query=args.q, limit=args.limit)
scripts/memory_tool.py:96:        store.log_event("dynamics_query_plan", agent=args.agent, order=consult_order, reward=reward)
workspace/scripts/test_intent_failure_taxonomy.py:30:            {"event": "router_fail", "detail": {"reason_code": "request_http_429"}},
workspace/scripts/test_intent_failure_taxonomy.py:31:            {"event": "router_escalate", "detail": {"reason_code": "request_http_429"}},
workspace/scripts/test_intent_failure_taxonomy.py:32:            {"event": "router_escalate", "detail": {"reason_code": "request_timeout"}},
workspace/scripts/test_intent_failure_taxonomy.py:33:            {"event": "router_skip", "detail": {"reason_code": "auth_login_required"}},
workspace/scripts/intent_failure_scan.py:97:ROUTER_EVENT_LOG = Path("itc/llm_router_events.jsonl")
workspace/scripts/intent_failure_scan.py:239:                if obj.get("event") not in ("router_fail", "router_escalate"):
workspace/scripts/intent_failure_scan.py:269:    router_stats = scan_router_events(ROUTER_EVENT_LOG)
workspace/scripts/intent_failure_scan.py:270:    lines.append(f"- router_failures: {router_stats.get('total', 0)}")
workspace/scripts/intent_failure_scan.py:272:        lines.append("- router_failure_reasons:")
workspace/scripts/intent_failure_scan.py:276:        lines.append("- router_failure_reasons: none")
workspace/scripts/team_chat.py:130:def log_event(
workspace/scripts/team_chat.py:230:        log_event(
workspace/scripts/team_chat.py:264:                log_event(
workspace/scripts/team_chat.py:277:            log_event(
workspace/scripts/team_chat.py:292:        log_event(
workspace/scripts/team_chat.py:305:            log_event(
workspace/scripts/team_chat.py:320:            log_event(
workspace/scripts/team_chat.py:331:        log_event(
workspace/scripts/team_chat.py:344:                log_event(
workspace/scripts/team_chat.py:372:            log_event(
workspace/scripts/team_chat.py:412:        log_event(
workspace/scripts/team_chat.py:437:    log_event(
workspace/scripts/report_token_burn.py:168:                if event == "router_escalate":
workspace/scripts/report_token_burn.py:174:                elif event == "router_attempt":
workspace/scripts/verify_policy_router.sh:86:        result = router.execute_with_escalation("itc_classify", {"prompt": "hello"}, validate_fn=lambda x: "news")
workspace/scripts/verify_policy_router.sh:127:        result = router.execute_with_escalation("coding", {"prompt": "x"}, validate_fn=lambda x: "news")
workspace/scripts/verify_policy_router.sh:131:        escalations = [json.loads(line) for line in events if '"router_escalate"' in line]
workspace/scripts/verify_policy_router.sh:150:        router.execute_with_escalation("itc_classify", {"prompt": "x"})
workspace/scripts/verify_policy_router.sh:151:        router.execute_with_escalation("itc_classify", {"prompt": "x"})
workspace/scripts/verify_policy_router.sh:152:        result = router.execute_with_escalation("itc_classify", {"prompt": "x"})
workspace/scripts/verify_policy_router.sh:173:        res_cap = router.execute_with_escalation("itc_classify", {"prompt": long_text})
workspace/scripts/verify_policy_router.sh:193:        res_ok = router.execute_with_escalation("itc_classify", {"prompt": "short"})
workspace/scripts/verify_policy_router.sh:195:        res_block = router.execute_with_escalation("itc_classify", {"prompt": "short"})
workspace/scripts/verify_policy_router.sh:229:            result = router.execute_with_escalation("itc_classify", {"prompt": "hello"}, validate_fn=lambda x: "news")
workspace/scripts/verify_policy_router.sh:233:            skips = [json.loads(line) for line in events if '"router_skip"' in line]
workspace/scripts/verify_policy_router.sh:263:            result = router.execute_with_escalation("itc_classify", {"prompt": "hello"})
workspace/scripts/verify_policy_router.sh:291:        result = router.execute_with_escalation("itc_classify", {"prompt": "hello"}, validate_fn=lambda x: "news")
workspace/scripts/team_chat_adapters.py:210:        result = self.router.execute_with_escalation(intent, payload, context_metadata=context, validate_fn=validate_fn)
workspace/scripts/policy_router.py:36:EVENT_LOG = BASE_DIR / "itc" / "llm_router_events.jsonl"
workspace/scripts/policy_router.py:38:TACTI_EVENT_LOG = BASE_DIR / "workspace" / "state" / "tacti_cr" / "events.jsonl"
workspace/scripts/policy_router.py:137:    log_event("policy_validation_warn", {"errors": errors[:12], "count": len(errors)})
workspace/scripts/policy_router.py:159:        log_event("active_inference_error", {"reason_code": f"{type(exc).__name__}"})
workspace/scripts/policy_router.py:394:            log_event("policy_load_fail", {"path": str(path)})
workspace/scripts/policy_router.py:410:            log_event("budget_load_fail", {"path": str(path)})
workspace/scripts/policy_router.py:429:            log_event("circuit_load_fail", {"path": str(path)})
workspace/scripts/policy_router.py:438:def log_event(event_type, detail=None, path=EVENT_LOG):
workspace/scripts/policy_router.py:454:    log_event(event_type, detail=detail, path=TACTI_EVENT_LOG)
workspace/scripts/policy_router.py:744:        event_log=EVENT_LOG,
workspace/scripts/policy_router.py:1166:    def execute_with_escalation(self, intent, payload, context_metadata=None, validate_fn=None):
workspace/scripts/policy_router.py:1183:            log_event(
workspace/scripts/policy_router.py:1196:            log_event(
workspace/scripts/policy_router.py:1197:                "router_route_selected",
workspace/scripts/policy_router.py:1209:            log_event(
workspace/scripts/policy_router.py:1210:                "router_route_selected",
workspace/scripts/policy_router.py:1227:                log_event("router_skip", {"intent": intent, "provider": name, "reason_code": last_reason}, self.event_log)
workspace/scripts/policy_router.py:1233:                log_event("router_skip", {"intent": intent, "provider": name, "reason_code": reason}, self.event_log)
workspace/scripts/policy_router.py:1245:                    log_event(
workspace/scripts/policy_router.py:1246:                        "router_skip",
workspace/scripts/policy_router.py:1254:                    log_event(
workspace/scripts/policy_router.py:1255:                        "router_skip",
workspace/scripts/policy_router.py:1263:                log_event("router_skip", {"intent": intent, "provider": name, "reason_code": "circuit_open"}, self.event_log)
workspace/scripts/policy_router.py:1286:                log_event(
workspace/scripts/policy_router.py:1287:                    "router_skip",
workspace/scripts/policy_router.py:1301:                log_event("router_skip", {"intent": intent, "provider": name, "reason_code": reason}, self.event_log)
workspace/scripts/policy_router.py:1340:                log_event(
workspace/scripts/policy_router.py:1341:                    "router_attempt",
workspace/scripts/policy_router.py:1352:                log_event(
workspace/scripts/policy_router.py:1353:                    "router_escalate",
workspace/scripts/policy_router.py:1373:                    log_event(
workspace/scripts/policy_router.py:1374:                        "router_attempt",
workspace/scripts/policy_router.py:1385:                    log_event(
workspace/scripts/policy_router.py:1386:                        "router_escalate",
workspace/scripts/policy_router.py:1398:            log_event(
workspace/scripts/policy_router.py:1399:                "router_success",
workspace/scripts/policy_router.py:1420:        log_event(
workspace/scripts/policy_router.py:1421:            "router_fail",

$ rg -n "audit|workspace/audit|hash|sha256|witness" -S .
./README.md:132:- **Audit Logs** — `workspace/audit/`
./workspace/briefs/itc_pipeline_integration.md:4:SIM_A currently runs pure regime logic and should remain unchanged. SIM_B currently derives ITC sentiment from tagged message JSONL without a stable source contract. This change adds a versioned ITC signal contract and ingestion boundary so SIM_B can consume deterministic, auditable sentiment/regime inputs now, and D_LIVE/E_SIM can reuse the same contract later.
./workspace/briefs/itc_pipeline_integration.md:9:- Persist raw + normalized artifacts with traceable hash linkage.
./workspace/briefs/itc_pipeline_integration.md:29:- `signature` (string, optional): content hash (`sha256:<hex>`)
./workspace/briefs/itc_pipeline_integration.md:44:- Raw: `workspace/artifacts/itc/raw/YYYY/MM/DD/<source>_<ts>_<hash8>.<ext>`
./workspace/briefs/itc_pipeline_integration.md:45:- Normalized: `workspace/artifacts/itc/normalized/YYYY/MM/DD/itc_signal_<ts>_<hash8>.json`
./workspace/briefs/itc_pipeline_integration.md:49:- Filenames derive from signal timestamp + content hash.
./AUDIT_SCOPE.md:1:# AUDIT_SCOPE.md — What Changed / What Needs Auditing
./AUDIT_SCOPE.md:3:Update this file after each admission or before each audit.
./AUDIT_SCOPE.md:15:- Audit protocol (this file, AUDIT_README.md, AUDIT_SNAPSHOT.md)
./AUDIT_SCOPE.md:21:- `workspace/AGENTS.md` — Multi-agent delegation section, audit pointer
./AUDIT_SCOPE.md:28:- `AUDIT_README.md` — Audit protocol constraints and strategy
./AUDIT_SCOPE.md:29:- `AUDIT_SCOPE.md` — This file
./AUDIT_SCOPE.md:30:- `AUDIT_SNAPSHOT.md` — Last audit signals
./AUDIT_SCOPE.md:39:## Audit Focus
./tests_unittest/test_goal_identity_invariants.py:50:                        "system2_audit": {"order": ladder, "allowPaid": False},
./reports/audit_journal.md:1:# Audit Journal (Append-Only)
./reports/audit_journal.md:3:Record notable changes, rationale, and follow-ups for audit continuity.
./reports/audit_journal.md:17:- **Purpose**: Initialize audit journal
./fixtures/system2_snapshot/status.json:9:    "path=/Users/demo/clawd/workspace/docs/audits/sample",
./docs/AFK_RUN_REPORT_2026-02-08_1357.md:64:- Ensure Telegram credentials (TG_API_ID, TG_API_HASH, TG_PHONE) are set in secrets.env (not committed).
./workspace/AUDIT_AIF_PHASE1_20260219.md:1:# AIF Phase 1 Audit (2026-02-19)
./workspace/policy/llm_policy.json:331:      "system2_audit": {
./workspace/dashboard/index.html:287:            { id: 2, title: 'Run security audit', priority: 'medium', status: 'pending', agent: 'system', time: '5m ago' },
./workspace/dashboard/index.html:302:            { name: 'Security Audit', cron: '0 9 * * 1', next: 'Mon 9:00 AM' },
./docs/HANDOFFS/HANDOFF-20260215-162339.md:47:- Revert the governance change commit via `git revert <hash>`.
./workspace/GOALS.md:3:## 🛡️ Codex Audit Targets (Hardening)
./docs/HANDOFFS/HANDOFF-20260216-061000-system2-audit-free-ladder.md:1:# System-2 Audit Free Ladder (Gemini -> Qwen -> Groq -> Ollama)
./docs/HANDOFFS/HANDOFF-20260216-061000-system2-audit-free-ladder.md:4:Make System-2 audit/governance/security intents route on a free ladder:
./docs/HANDOFFS/HANDOFF-20260216-061000-system2-audit-free-ladder.md:15:  - `routing.intents.{system2_audit,governance,security}.order` matches the same list
./workspace/tacti_cr/semantic_immune.py:5:import hashlib
./workspace/tacti_cr/semantic_immune.py:23:        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
./workspace/tacti_cr/semantic_immune.py:106:    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
./workspace/tacti_cr/semantic_immune.py:110:        "content_hash": digest,
./workspace/tacti_cr/semantic_immune.py:131:def approve_quarantine(repo_root: Path, content_hash: str) -> dict[str, Any]:
./workspace/tacti_cr/semantic_immune.py:133:    target = str(content_hash)
./workspace/tacti_cr/semantic_immune.py:146:        if str(row.get("content_hash")) == target and approved is None:
./workspace/tacti_cr/semantic_immune.py:156:        return {"ok": False, "reason": "not_found", "content_hash": target}
./workspace/tacti_cr/semantic_immune.py:158:    _append(paths["approvals"], {"ts": _utc_now(), "content_hash": target, "approved": True})
./workspace/tacti_cr/semantic_immune.py:160:    return {"ok": True, "content_hash": target}
./tests_unittest/test_itc_pipeline.py:83:            "signature": "sha256:" + "a" * 64,
./tests_unittest/test_tacti_cr_novel_10.py:102:                "[15:00] Added concise audit runbook for reviewers.\n",
./tests_unittest/test_tacti_cr_novel_10.py:121:            approved = approve_quarantine(root, out["content_hash"])
./workspace/handoffs/audit_2026-02-08.md:1:# Audit 2026-02-08
./workspace/handoffs/audit_2026-02-08.md:4:Full system audit (architecture, agents, routing, budgets, logs, failure points).
./docs/HANDOFFS/HANDOFF-20260216-003433-compaction-gate-audit.md:1:# Handoff: System-2 Dispatch Compaction Gate + Request-Size Audit
./docs/HANDOFFS/HANDOFF-20260216-003433-compaction-gate-audit.md:15:1. **Secret-safe request shape audit events** before each provider call:
./docs/HANDOFFS/HANDOFF-20260216-003433-compaction-gate-audit.md:23:4. **Audit trail when all candidates fail** via an emitted summary event.
./workspace/handoffs/audit_protocol_impl_2026-02-06.md:1:# Handoff: Audit Protocol Implementation
./workspace/handoffs/audit_protocol_impl_2026-02-06.md:10:| `AUDIT_README.md` | Constraints, strategy, exclusions for auditors |
./workspace/handoffs/audit_protocol_impl_2026-02-06.md:11:| `AUDIT_SCOPE.md` | Structured template: last commit, changed areas, focus, skip-if-pass |
./workspace/handoffs/audit_protocol_impl_2026-02-06.md:12:| `AUDIT_SNAPSHOT.md` | Compact last-audit signals (commit, pass/fail, gateway, cron, agents) |
./workspace/handoffs/audit_protocol_impl_2026-02-06.md:19:| `workspace/CLAUDE_CODE.md` | Added Audit Entrypoint section before Session Protocol |
./workspace/handoffs/audit_protocol_impl_2026-02-06.md:20:| `workspace/AGENTS.md` | Added audit pointer line in delegation Rules |
./workspace/handoffs/audit_protocol_impl_2026-02-06.md:24:1. **Audit protocol** (AUDIT_README.md): security-first, governance-first, delta-first, no scope creep. Outputs to `workspace/handoffs/audit_YYYY-MM-DD.md`.
./workspace/handoffs/audit_protocol_impl_2026-02-06.md:27:4. **Agent discoverability**: Both CLAUDE_CODE.md and AGENTS.md now point to AUDIT_README.md + AUDIT_SCOPE.md as audit entrypoints.
./workspace/handoffs/audit_protocol_impl_2026-02-06.md:38:2. **AUDIT_SCOPE.md is manual**: Must be updated by the auditor before each audit. No automation enforces this yet.
./workspace/handoffs/audit_protocol_impl_2026-02-06.md:41:5. **Audit cron job not yet created**: The daily regression cron exists, but there is no periodic audit cron. Current design is manual/on-demand audits only, which is appropriate for now.
./workspace/handoffs/handoff_2026-02-18_clawd_ingress_audit.md:1:# Handoff: C_Lawd Telegram + WebUI Non-Response Audit (2026-02-18)
./workspace/handoffs/handoff_2026-02-18_clawd_ingress_audit.md:4:- Audit time: 2026-02-18T10:02:54+10:00 to 2026-02-18T10:26:xx+10:00
./workspace/handoffs/handoff_2026-02-18_clawd_ingress_audit.md:60:- Sensitive values were intentionally redacted in this audit narrative.
./docs/INDEX.json:58:      "name": "AUDIT_README.md",
./docs/INDEX.json:62:      "name": "AUDIT_SCOPE.md",
./docs/INDEX.json:66:      "name": "AUDIT_SNAPSHOT.md",
./docs/INDEX.json:170:    "AUDIT_README.md",
./docs/INDEX.json:171:    "AUDIT_SCOPE.md",
./docs/INDEX.json:172:    "AUDIT_SNAPSHOT.md",
./docs/INDEX.json:247:    "reports/audit_journal.md",
./docs/INDEX.json:258:    "scripts/redact_audit_evidence.js",
./docs/INDEX.json:283:    "tests/redact_audit_evidence.test.js",
./docs/INDEX.json:314:    "workspace/docs/audits/MERGE-EXEC2-2026-02-12.md",
./docs/INDEX.json:315:    "workspace/docs/audits/NEXTSTEPS-EXEC2-2026-02-12.md",
./docs/INDEX.json:316:    "workspace/docs/audits/POSTMERGE-VALIDATION-2026-02-12.md",
./docs/INDEX.json:317:    "workspace/docs/audits/QUARANTINE-BUNDLE-2026-02-12/RESTORE.md",
./docs/INDEX.json:318:    "workspace/docs/audits/QUARANTINE-BUNDLE-2026-02-12/all_changed_paths_raw.txt",
./docs/INDEX.json:319:    "workspace/docs/audits/QUARANTINE-BUNDLE-2026-02-12/all_changed_paths_source_only.txt",
./docs/INDEX.json:320:    "workspace/docs/audits/QUARANTINE-BUNDLE-2026-02-12/bundle_manifest.json",
./docs/INDEX.json:321:    "workspace/docs/audits/QUARANTINE-BUNDLE-2026-02-12/category_counts_raw.tsv",
./docs/INDEX.json:322:    "workspace/docs/audits/QUARANTINE-BUNDLE-2026-02-12/category_counts_source_only.tsv",
./docs/INDEX.json:323:    "workspace/docs/audits/QUARANTINE-BUNDLE-2026-02-12/diff_stat.txt",
```

### Canonical Paths

- policy_router: \
- arousal estimator: \
- valence engine: \
- dream consolidation: \
- temporal episodic memory: \
- semantic immune / contradiction gate: \
- hivemind trails: \
- hivemind reservoir: \
- hivemind peer graph: \
- active inference model: \
- router event log path: \ (via EVENT_LOG in policy_router)
- TACTI event log path: \ (via TACTI_EVENT_LOG in policy_router)
- existing audit directory: \

### Current Event Schema Notes

- Router/TACTI logs are append-only JSONL lines with keys: \, \, optional \.
- Routing decisions are emitted from \ via \ calls for \, \, \, \, \, \.

## Phase 1 Discovery (Corrected)

```text
$ rg -n "dream_consolidation|temporal\.py|reservoir\.py|trails\.py|peer_graph\.py|active_inference|semantic_immune|arousal_oscillator|valence" -S .
./memory/2026-02-19.md:11:- File: `workspace/research/active_inference_research.md`
./README.md:27:- **`peer_graph.py`** — Murmuration-style sparse peer connections (each agent tracks ~7 neighbors)
./README.md:29:- **`reservoir.py`** — Echo-state reservoir computing for temporal pattern processing
./README.md:30:- **`trails.py`** — External memory with decay and reinforcement (like slime trails)
./workspace/CODEX_Source_UI_TACTI_Upgrade.md:28:| **Dream Consolidation** | `workspace/tacti_cr/dream_consolidation.py` | Memory consolidation status, last run |
./workspace/CODEX_Source_UI_TACTI_Upgrade.md:30:| **Semantic Immune** | `workspace/tacti_cr/semantic_immune.py` | Quarantine stats, recent blocks |
./workspace/CODEX_Source_UI_TACTI_Upgrade.md:31:| **Arousal Oscillator** | `workspace/tacti_cr/arousal_oscillator.py` | Current energy level, hourly histogram |
./workspace/CODEX_Source_UI_TACTI_Upgrade.md:32:| **Trail Memory** | `workspace/hivemind/hivemind/trails.py` | Memory heatmap, recent trails |
./workspace/CODEX_Source_UI_TACTI_Upgrade.md:33:| **HiveMind Peer Graph** | `workspace/hivemind/hivemind/peer_graph.py` | Agent connections visualization |
./workspace/CODEX_Source_UI_TACTI_Upgrade.md:115:- Backend API exists: `workspace/source-ui/api/trails.py`
./workspace/AUDIT_AIF_PHASE1_20260219.md:10:  - `workspace/tacti_cr/active_inference_agent.py`
./workspace/AUDIT_AIF_PHASE1_20260219.md:29:  - `python3 -m py_compile workspace/tacti_cr/external_memory.py workspace/tacti_cr/efe_calculator.py workspace/tacti_cr/curiosity.py workspace/tacti_cr/active_inference_agent.py workspace/scripts/external_memory_demo.py` (pass)
./workspace/policy/expression_manifest.json:11:      "feature_name": "dream_consolidation",
./workspace/policy/expression_manifest.json:17:      "feature_name": "semantic_immune",
./workspace/policy/expression_manifest.json:24:      "activation_conditions": {"valence_min": -0.2},
./tests_unittest/test_hivemind_active_inference.py:13:from hivemind.active_inference import PreferenceModel  # noqa: E402
./tests_unittest/test_tacti_cr_novel_10.py:20:from tacti_cr.arousal_oscillator import ArousalOscillator
./tests_unittest/test_tacti_cr_novel_10.py:21:from tacti_cr.dream_consolidation import run_consolidation
./tests_unittest/test_tacti_cr_novel_10.py:25:from tacti_cr.semantic_immune import assess_content, approve_quarantine
./tests_unittest/test_tacti_cr_novel_10.py:27:from tacti_cr.valence import current_valence, routing_bias, update_valence
./tests_unittest/test_tacti_cr_novel_10.py:44:    def test_arousal_oscillator_bins_and_explain(self):
./tests_unittest/test_tacti_cr_novel_10.py:67:                json.dumps({"features": [{"feature_name": "prefetch", "activation_conditions": {"valence_min": -0.1}, "suppression_conditions": {}, "priority": 1}]}, indent=2),
./tests_unittest/test_tacti_cr_novel_10.py:73:                {"valence": 0.2, "budget_remaining": 0.9, "local_available": True},
./tests_unittest/test_tacti_cr_novel_10.py:94:    def test_dream_consolidation_stable(self):
./tests_unittest/test_tacti_cr_novel_10.py:105:            os.environ["TACTI_CR_DREAM_CONSOLIDATION"] = "1"
./tests_unittest/test_tacti_cr_novel_10.py:113:    def test_semantic_immune_quarantine_and_approve(self):
./tests_unittest/test_tacti_cr_novel_10.py:116:            os.environ["TACTI_CR_SEMANTIC_IMMUNE"] = "1"
./tests_unittest/test_tacti_cr_novel_10.py:136:    def test_mirror_and_valence_local_state(self):
./tests_unittest/test_tacti_cr_novel_10.py:140:            os.environ["TACTI_CR_VALENCE"] = "1"
./tests_unittest/test_tacti_cr_novel_10.py:144:            update_valence("coder", {"failed": True, "retry_loops": 2}, repo_root=root)
./tests_unittest/test_tacti_cr_novel_10.py:145:            val = current_valence("coder", repo_root=root)
./workspace/CODEX_TASK_LIST.md:58:**File:** `workspace/tacti_cr/active_inference_agent.py`
./scripts/daily_technique.py:92:        "benefits": ["Integrates shadow", "Resolves ambivalence", "Builds self-compassion"],
./workspace/tacti_cr/valence.py:1:"""Affective valence engine with half-life decay and routing bias signals."""
./workspace/tacti_cr/valence.py:16:    return root / "workspace" / "state" / "valence" / f"{agent}.json"
./workspace/tacti_cr/valence.py:29:        return {"valence": 0.0, "updated_at": _now().isoformat()}
./workspace/tacti_cr/valence.py:36:    return {"valence": 0.0, "updated_at": _now().isoformat()}
./workspace/tacti_cr/valence.py:44:def current_valence(agent: str, *, repo_root: Path | None = None, now: datetime | None = None) -> float:
./workspace/tacti_cr/valence.py:45:    if not is_enabled("valence"):
./workspace/tacti_cr/valence.py:52:    half_life = get_float("valence_half_life_hours", 6.0, clamp=(0.5, 48.0))
./workspace/tacti_cr/valence.py:53:    decayed = float(data.get("valence", 0.0)) * math.exp(-math.log(2.0) * age_hours / half_life)
./workspace/tacti_cr/valence.py:57:def update_valence(agent: str, outcome: dict[str, Any], *, repo_root: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
./workspace/tacti_cr/valence.py:58:    if not is_enabled("valence"):
./workspace/tacti_cr/valence.py:59:        return {"ok": False, "reason": "valence_disabled", "valence": 0.0}
./workspace/tacti_cr/valence.py:61:    value = current_valence(agent, repo_root=repo_root, now=dt_now)
./workspace/tacti_cr/valence.py:72:    payload = {"agent": agent, "valence": value, "updated_at": dt_now.isoformat().replace("+00:00", "Z")}
./workspace/tacti_cr/valence.py:74:    return {"ok": True, "valence": value}
./workspace/tacti_cr/valence.py:78:    value = current_valence(agent, repo_root=repo_root)
./workspace/tacti_cr/valence.py:80:        "valence": value,
./workspace/tacti_cr/valence.py:87:__all__ = ["current_valence", "update_valence", "routing_bias"]
./workspace/tacti_cr/semantic_immune.py:43:    base = repo_root / "workspace" / "state" / "semantic_immune"
./workspace/tacti_cr/semantic_immune.py:90:    if not is_enabled("semantic_immune"):
./workspace/tacti_cr/semantic_immune.py:91:        return {"ok": True, "reason": "semantic_immune_disabled", "quarantined": False}
./workspace/tacti_cr/expression.py:42:    if name == "valence_min":
./workspace/tacti_cr/expression.py:43:        return float(context.get("valence", 0.0)) >= float(cond)
./workspace/tacti_cr/expression.py:44:    if name == "valence_max":
./workspace/tacti_cr/expression.py:45:        return float(context.get("valence", 0.0)) <= float(cond)
./workspace/tacti_cr/expression.py:99:    # Global negative valence guard to prefer local/low-risk behavior.
./workspace/tacti_cr/expression.py:100:    neg_guard = get_float("valence_negative_guard", -0.35, clamp=(-1.0, 1.0))
./workspace/tacti_cr/expression.py:101:    if float(local_ctx.get("valence", 0.0)) <= neg_guard:
./workspace/tacti_cr/expression.py:102:        reasons.setdefault("_global", []).append("negative_valence_guard")
./tests_unittest/test_policy_router_active_inference_hook.py:19:    def test_active_inference_predict_and_update_in_execute(self):
./tests_unittest/test_policy_router_active_inference_hook.py:25:            ai_state = tmp / "active_inference_state.json"
./tests_unittest/test_policy_router_active_inference_hook.py:33:                "ENABLE_ACTIVE_INFERENCE": "1",
./tests_unittest/test_policy_router_active_inference_hook.py:37:                with patch.object(policy_router, "ACTIVE_INFERENCE_STATE_PATH", ai_state):
./tests_unittest/test_policy_router_active_inference_hook.py:55:            self.assertIn("active_inference", captured["context_metadata"])
./tests_unittest/test_policy_router_active_inference_hook.py:56:            ai = captured["context_metadata"]["active_inference"]
./workspace/tacti_cr/README.md:11:- `temporal.py`
./workspace/tacti_cr/README.md:67:- `test_tacti_cr_temporal.py`
./workspace/tacti_cr/README.md:84:- `TACTI_CR_DREAM_CONSOLIDATION=1`
./workspace/tacti_cr/README.md:85:- `TACTI_CR_SEMANTIC_IMMUNE=1`
./workspace/tacti_cr/README.md:90:- `TACTI_CR_VALENCE=1`
./workspace/tacti_cr/README.md:107:bash workspace/scripts/dream_consolidation.sh 2026-02-19
./workspace/tacti_cr/__init__.py:16:from .active_inference_agent import ActiveInferenceAgent
./workspace/tacti_cr/__init__.py:19:from .arousal_oscillator import ArousalOscillator
./workspace/tacti_cr/__init__.py:21:from .dream_consolidation import run_consolidation
./workspace/tacti_cr/__init__.py:22:from .semantic_immune import assess_content, approve_quarantine
./workspace/tacti_cr/__init__.py:24:from .valence import current_valence, update_valence, routing_bias
./workspace/tacti_cr/__init__.py:62:    "current_valence",
./workspace/tacti_cr/__init__.py:63:    "update_valence",

$ rg -n "router_(route_selected|attempt|skip|success|escalate|fail)|log_event\(|EVENT_LOG|execute_with_escalation" workspace/scripts core scripts
scripts/memory_tool.py:69:    store.log_event("query", agent=args.agent, query=args.q, limit=args.limit)
scripts/memory_tool.py:96:        store.log_event("dynamics_query_plan", agent=args.agent, order=consult_order, reward=reward)
scripts/itc_classify.py:44:EVENT_LOG = BASE_DIR / "itc" / "classify_events.jsonl"
scripts/itc_classify.py:82:def log_event(event_type, detail=None):
scripts/itc_classify.py:84:    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
scripts/itc_classify.py:92:        with open(EVENT_LOG, "a", encoding="utf-8") as f:
scripts/itc_classify.py:156:    result = router.execute_with_escalation(
scripts/itc_classify.py:225:    log_event("classify_start", {
scripts/itc_classify.py:270:                    log_event("llm_router_fail", {"reason_code": llm_backend})
scripts/itc_classify.py:293:    log_event("classify_done", {
workspace/scripts/team_chat.py:130:def log_event(
workspace/scripts/team_chat.py:230:        log_event(
workspace/scripts/team_chat.py:264:                log_event(
workspace/scripts/team_chat.py:277:            log_event(
workspace/scripts/team_chat.py:292:        log_event(
workspace/scripts/team_chat.py:305:            log_event(
workspace/scripts/team_chat.py:320:            log_event(
workspace/scripts/team_chat.py:331:        log_event(
workspace/scripts/team_chat.py:344:                log_event(
workspace/scripts/team_chat.py:372:            log_event(
workspace/scripts/team_chat.py:412:        log_event(
workspace/scripts/team_chat.py:437:    log_event(
workspace/scripts/test_intent_failure_taxonomy.py:30:            {"event": "router_fail", "detail": {"reason_code": "request_http_429"}},
workspace/scripts/test_intent_failure_taxonomy.py:31:            {"event": "router_escalate", "detail": {"reason_code": "request_http_429"}},
workspace/scripts/test_intent_failure_taxonomy.py:32:            {"event": "router_escalate", "detail": {"reason_code": "request_timeout"}},
workspace/scripts/test_intent_failure_taxonomy.py:33:            {"event": "router_skip", "detail": {"reason_code": "auth_login_required"}},
workspace/scripts/report_token_burn.py:168:                if event == "router_escalate":
workspace/scripts/report_token_burn.py:174:                elif event == "router_attempt":
workspace/scripts/team_chat_adapters.py:210:        result = self.router.execute_with_escalation(intent, payload, context_metadata=context, validate_fn=validate_fn)
workspace/scripts/intent_failure_scan.py:97:ROUTER_EVENT_LOG = Path("itc/llm_router_events.jsonl")
workspace/scripts/intent_failure_scan.py:239:                if obj.get("event") not in ("router_fail", "router_escalate"):
workspace/scripts/intent_failure_scan.py:269:    router_stats = scan_router_events(ROUTER_EVENT_LOG)
workspace/scripts/intent_failure_scan.py:270:    lines.append(f"- router_failures: {router_stats.get('total', 0)}")
workspace/scripts/intent_failure_scan.py:272:        lines.append("- router_failure_reasons:")
workspace/scripts/intent_failure_scan.py:276:        lines.append("- router_failure_reasons: none")
workspace/scripts/policy_router.py:36:EVENT_LOG = BASE_DIR / "itc" / "llm_router_events.jsonl"
workspace/scripts/policy_router.py:38:TACTI_EVENT_LOG = BASE_DIR / "workspace" / "state" / "tacti_cr" / "events.jsonl"
workspace/scripts/policy_router.py:137:    log_event("policy_validation_warn", {"errors": errors[:12], "count": len(errors)})
workspace/scripts/policy_router.py:159:        log_event("active_inference_error", {"reason_code": f"{type(exc).__name__}"})
workspace/scripts/policy_router.py:394:            log_event("policy_load_fail", {"path": str(path)})
workspace/scripts/policy_router.py:410:            log_event("budget_load_fail", {"path": str(path)})
workspace/scripts/policy_router.py:429:            log_event("circuit_load_fail", {"path": str(path)})
workspace/scripts/policy_router.py:438:def log_event(event_type, detail=None, path=EVENT_LOG):
workspace/scripts/policy_router.py:454:    log_event(event_type, detail=detail, path=TACTI_EVENT_LOG)
workspace/scripts/policy_router.py:744:        event_log=EVENT_LOG,
workspace/scripts/policy_router.py:1166:    def execute_with_escalation(self, intent, payload, context_metadata=None, validate_fn=None):
workspace/scripts/policy_router.py:1183:            log_event(
workspace/scripts/policy_router.py:1196:            log_event(
workspace/scripts/policy_router.py:1197:                "router_route_selected",
workspace/scripts/policy_router.py:1209:            log_event(
workspace/scripts/policy_router.py:1210:                "router_route_selected",
workspace/scripts/policy_router.py:1227:                log_event("router_skip", {"intent": intent, "provider": name, "reason_code": last_reason}, self.event_log)
workspace/scripts/policy_router.py:1233:                log_event("router_skip", {"intent": intent, "provider": name, "reason_code": reason}, self.event_log)
workspace/scripts/policy_router.py:1245:                    log_event(
workspace/scripts/policy_router.py:1246:                        "router_skip",
workspace/scripts/policy_router.py:1254:                    log_event(
workspace/scripts/policy_router.py:1255:                        "router_skip",
workspace/scripts/policy_router.py:1263:                log_event("router_skip", {"intent": intent, "provider": name, "reason_code": "circuit_open"}, self.event_log)
workspace/scripts/policy_router.py:1286:                log_event(
workspace/scripts/policy_router.py:1287:                    "router_skip",
workspace/scripts/policy_router.py:1301:                log_event("router_skip", {"intent": intent, "provider": name, "reason_code": reason}, self.event_log)
workspace/scripts/policy_router.py:1340:                log_event(
workspace/scripts/policy_router.py:1341:                    "router_attempt",
workspace/scripts/policy_router.py:1352:                log_event(
workspace/scripts/policy_router.py:1353:                    "router_escalate",
workspace/scripts/policy_router.py:1373:                    log_event(
workspace/scripts/policy_router.py:1374:                        "router_attempt",
workspace/scripts/policy_router.py:1385:                    log_event(
workspace/scripts/policy_router.py:1386:                        "router_escalate",
workspace/scripts/policy_router.py:1398:            log_event(
workspace/scripts/policy_router.py:1399:                "router_success",
workspace/scripts/policy_router.py:1420:        log_event(
workspace/scripts/policy_router.py:1421:            "router_fail",
workspace/scripts/verify_policy_router.sh:86:        result = router.execute_with_escalation("itc_classify", {"prompt": "hello"}, validate_fn=lambda x: "news")
workspace/scripts/verify_policy_router.sh:127:        result = router.execute_with_escalation("coding", {"prompt": "x"}, validate_fn=lambda x: "news")
workspace/scripts/verify_policy_router.sh:131:        escalations = [json.loads(line) for line in events if '"router_escalate"' in line]
workspace/scripts/verify_policy_router.sh:150:        router.execute_with_escalation("itc_classify", {"prompt": "x"})
workspace/scripts/verify_policy_router.sh:151:        router.execute_with_escalation("itc_classify", {"prompt": "x"})
workspace/scripts/verify_policy_router.sh:152:        result = router.execute_with_escalation("itc_classify", {"prompt": "x"})
workspace/scripts/verify_policy_router.sh:173:        res_cap = router.execute_with_escalation("itc_classify", {"prompt": long_text})
workspace/scripts/verify_policy_router.sh:193:        res_ok = router.execute_with_escalation("itc_classify", {"prompt": "short"})
workspace/scripts/verify_policy_router.sh:195:        res_block = router.execute_with_escalation("itc_classify", {"prompt": "short"})
workspace/scripts/verify_policy_router.sh:229:            result = router.execute_with_escalation("itc_classify", {"prompt": "hello"}, validate_fn=lambda x: "news")
workspace/scripts/verify_policy_router.sh:233:            skips = [json.loads(line) for line in events if '"router_skip"' in line]
workspace/scripts/verify_policy_router.sh:263:            result = router.execute_with_escalation("itc_classify", {"prompt": "hello"})
workspace/scripts/verify_policy_router.sh:291:        result = router.execute_with_escalation("itc_classify", {"prompt": "hello"}, validate_fn=lambda x: "news")

$ rg -n "audit|workspace/audit|hash|sha256|witness" -S .
./reports/audit_journal.md:1:# Audit Journal (Append-Only)
./reports/audit_journal.md:3:Record notable changes, rationale, and follow-ups for audit continuity.
./reports/audit_journal.md:17:- **Purpose**: Initialize audit journal
./package.json:9:    "redact:audit-evidence": "node scripts/redact_audit_evidence.js",
./package.json:10:    "check:redaction-fixtures": "node scripts/redact_audit_evidence.js --in fixtures/redaction/in --out .tmp/redaction_out --json --dry-run",
./README.md:132:- **Audit Logs** — `workspace/audit/`
./AUDIT_SCOPE.md:1:# AUDIT_SCOPE.md — What Changed / What Needs Auditing
./AUDIT_SCOPE.md:3:Update this file after each admission or before each audit.
./AUDIT_SCOPE.md:15:- Audit protocol (this file, AUDIT_README.md, AUDIT_SNAPSHOT.md)
./AUDIT_SCOPE.md:21:- `workspace/AGENTS.md` — Multi-agent delegation section, audit pointer
./AUDIT_SCOPE.md:28:- `AUDIT_README.md` — Audit protocol constraints and strategy
./AUDIT_SCOPE.md:29:- `AUDIT_SCOPE.md` — This file
./AUDIT_SCOPE.md:30:- `AUDIT_SNAPSHOT.md` — Last audit signals
./AUDIT_SCOPE.md:39:## Audit Focus
./docs/AFK_RUN_REPORT_2026-02-08_1357.md:64:- Ensure Telegram credentials (TG_API_ID, TG_API_HASH, TG_PHONE) are set in secrets.env (not committed).
./tests_unittest/test_goal_identity_invariants.py:50:                        "system2_audit": {"order": ladder, "allowPaid": False},
./docs/claude/NOTES_SYSTEM2_20260217.md:3:This note is evidence-based from the current branch and repository paths. It is not an exhaustive codebase audit.
./docs/claude/NOTES_SYSTEM2_20260217.md:11:2. `7f72687` `harden(integrity): enforce governance hash anchors at runtime`
./docs/claude/UPDATE_PLAN_20260217.md:24:- Acceptance: fail-closed on hash drift, explicit approval updates baseline
./docs/SECRET_SCRUB.md:1:# Secret Scrub & Audit Runbook
./docs/SECRET_SCRUB.md:16:- `scrub_history_candidates.txt` (commit hashes + candidate paths)
./scripts/gateway_inspect.ps1:45:function Get-Sha256Hex {
./scripts/gateway_inspect.ps1:49:  $sha = [System.Security.Cryptography.SHA256]::Create()
./scripts/gateway_inspect.ps1:51:    $hash = $sha.ComputeHash($bytes)
./scripts/gateway_inspect.ps1:52:    return ([System.BitConverter]::ToString($hash)).Replace("-", "").ToLowerInvariant()
./scripts/gateway_inspect.ps1:143:  param([string]$needle, [hashtable]$stringsBySection)
./scripts/gateway_inspect.ps1:317:          CommandLineSha256 = (Get-Sha256Hex (Redact-Text $cmd))
./scripts/gateway_inspect.ps1:422:        ArgumentsSha256  = (Get-Sha256Hex (Redact-Text ([string]$args)))
./scripts/gateway_inspect.ps1:548:      $prevCmdHashes = @()
./scripts/gateway_inspect.ps1:549:      $currCmdHashes = @()
./scripts/gateway_inspect.ps1:550:      try { $prevCmdHashes = @($prev.inspection.listener.processes | ForEach-Object { [string]$_.CommandLineSha256 }) } catch {}
./scripts/gateway_inspect.ps1:551:      try { $currCmdHashes = @($report.inspection.listener.processes | ForEach-Object { [string]$_.CommandLineSha256 }) } catch {}
./scripts/gateway_inspect.ps1:552:      $diffObj.listener.commandLineChanged = -not (@($prevCmdHashes) -join "," -eq @($currCmdHashes) -join ",")
./scripts/gateway_inspect.ps1:562:      $prevSet = [System.Collections.Generic.HashSet[string]]::new()
./scripts/gateway_inspect.ps1:564:      $currSet = [System.Collections.Generic.HashSet[string]]::new()
./scripts/gateway_inspect.ps1:604:          $pArgsHash = if ($pa) { [string]$pa.ArgumentsSha256 } else { "" }
./scripts/gateway_inspect.ps1:605:          $cArgsHash = if ($ca) { [string]$ca.ArgumentsSha256 } else { "" }
./scripts/gateway_inspect.ps1:609:          if ($pExec -ne $cExec -or $pArgsHash -ne $cArgsHash -or $pWd -ne $cWd) {
./scripts/gateway_inspect.ps1:613:              previous = [ordered]@{ Execute = $pExec; ArgumentsSha256 = $pArgsHash; WorkingDirectory = $pWd }
./scripts/gateway_inspect.ps1:614:              current  = [ordered]@{ Execute = $cExec; ArgumentsSha256 = $cArgsHash; WorkingDirectory = $cWd }
./scripts/gateway_inspect.ps1:641:      $diffLines.Add(("CommandLine changed (redacted hash): {0}" -f $diffObj.listener.commandLineChanged)) | Out-Null
./AUDIT_README.md:1:# AUDIT_README.md — Read Before You Audit
./AUDIT_README.md:6:- **Governance-first**: Audits observe and report. No out-of-band remediation. Fix proposals go through the Change Admission Gate (Design Brief -> Implementation -> Regression/Verify -> Admission).
./AUDIT_README.md:7:- **Token efficiency**: Delta-first. Never re-audit unchanged subsystems when regressions/verify pass.
./AUDIT_README.md:10:## Audit Strategy
./AUDIT_README.md:12:1. **Read scope** — Open `AUDIT_SCOPE.md` to see what changed since last admitted commit.
./AUDIT_README.md:13:2. **Run regressions** — `bash workspace/scripts/regression.sh` then `bash workspace/scripts/verify.sh`. If both pass, skip areas listed under `audit_skip_if_all_checks_pass`.
./AUDIT_README.md:14:3. **Audit touched areas** — Focus only on `audit_focus` items from AUDIT_SCOPE.md. Expand scope only if a failure implicates another subsystem.
./AUDIT_README.md:15:4. **Write output** — One file: `workspace/handoffs/audit_YYYY-MM-DD.md`. Contains findings, pass/fail per area, and any remediation proposals (as Design Brief references, not inline fixes).
./AUDIT_README.md:16:5. **Update snapshot** — After audit completes, update `AUDIT_SNAPSHOT.md` with current signals.
./AUDIT_README.md:21:workspace/handoffs/audit_YYYY-MM-DD.md
./AUDIT_README.md:26:- No refactoring during audits.
./AUDIT_README.md:28:- No scope creep beyond `audit_focus`.
./docs/HANDOFFS/HANDOFF-20260216-003433-compaction-gate-audit.md:1:# Handoff: System-2 Dispatch Compaction Gate + Request-Size Audit
./docs/HANDOFFS/HANDOFF-20260216-003433-compaction-gate-audit.md:15:1. **Secret-safe request shape audit events** before each provider call:
./docs/HANDOFFS/HANDOFF-20260216-003433-compaction-gate-audit.md:23:4. **Audit trail when all candidates fail** via an emitted summary event.
./docs/HANDOFFS/HANDOFF-20260215-162339.md:47:- Revert the governance change commit via `git revert <hash>`.
./tests_unittest/test_hivemind_reservoir.py:28:        s1 = r1.step({"intent": "audit"}, {"agent": "main"}, {"deg": 3})
./tests_unittest/test_hivemind_reservoir.py:29:        s2 = r2.step({"intent": "audit"}, {"agent": "main"}, {"deg": 3})
./docs/INDEX.json:58:      "name": "AUDIT_README.md",
./docs/INDEX.json:62:      "name": "AUDIT_SCOPE.md",
./docs/INDEX.json:66:      "name": "AUDIT_SNAPSHOT.md",
./docs/INDEX.json:170:    "AUDIT_README.md",
./docs/INDEX.json:171:    "AUDIT_SCOPE.md",
./docs/INDEX.json:172:    "AUDIT_SNAPSHOT.md",
./docs/INDEX.json:247:    "reports/audit_journal.md",
./docs/INDEX.json:258:    "scripts/redact_audit_evidence.js",
./docs/INDEX.json:283:    "tests/redact_audit_evidence.test.js",
./docs/INDEX.json:314:    "workspace/docs/audits/MERGE-EXEC2-2026-02-12.md",
./docs/INDEX.json:315:    "workspace/docs/audits/NEXTSTEPS-EXEC2-2026-02-12.md",
./docs/INDEX.json:316:    "workspace/docs/audits/POSTMERGE-VALIDATION-2026-02-12.md",
./docs/INDEX.json:317:    "workspace/docs/audits/QUARANTINE-BUNDLE-2026-02-12/RESTORE.md",
./docs/INDEX.json:318:    "workspace/docs/audits/QUARANTINE-BUNDLE-2026-02-12/all_changed_paths_raw.txt",
./docs/INDEX.json:319:    "workspace/docs/audits/QUARANTINE-BUNDLE-2026-02-12/all_changed_paths_source_only.txt",
./docs/INDEX.json:320:    "workspace/docs/audits/QUARANTINE-BUNDLE-2026-02-12/bundle_manifest.json",
./docs/INDEX.json:321:    "workspace/docs/audits/QUARANTINE-BUNDLE-2026-02-12/category_counts_raw.tsv",
./docs/INDEX.json:322:    "workspace/docs/audits/QUARANTINE-BUNDLE-2026-02-12/category_counts_source_only.tsv",
./docs/INDEX.json:323:    "workspace/docs/audits/QUARANTINE-BUNDLE-2026-02-12/diff_stat.txt",
./docs/INDEX.json:324:    "workspace/docs/audits/QUARANTINE-BUNDLE-2026-02-12/name_status.txt",
./docs/INDEX.json:325:    "workspace/docs/audits/QUARANTINE-BUNDLE-2026-02-12/numstat_sorted.tsv",
```

### Canonical Paths

- policy_router: `workspace/scripts/policy_router.py`
- arousal estimator: `workspace/tacti_cr/arousal_oscillator.py`
- valence engine: `workspace/tacti_cr/valence.py`
- dream consolidation: `workspace/tacti_cr/dream_consolidation.py`
- temporal episodic memory: `workspace/tacti_cr/temporal.py`
- semantic immune / contradiction gate: `workspace/tacti_cr/semantic_immune.py`
- hivemind trails: `workspace/hivemind/hivemind/trails.py`
- hivemind reservoir: `workspace/hivemind/hivemind/reservoir.py`
- hivemind peer graph: `workspace/hivemind/hivemind/peer_graph.py`
- active inference model: `workspace/hivemind/hivemind/active_inference.py`
- router event log path: `itc/llm_router_events.jsonl` (via EVENT_LOG in policy_router)
- TACTI event log path: `workspace/state/tacti_cr/events.jsonl` (via TACTI_EVENT_LOG in policy_router)
- existing audit directory: `workspace/audit/`

### Current Event Schema Notes

- Router/TACTI logs are append-only JSONL lines with keys: `ts`, `event`, optional `detail`.
- Routing decisions are emitted from `PolicyRouter.execute_with_escalation()` via `log_event()` calls for `router_route_selected`, `router_skip`, `router_attempt`, `router_escalate`, `router_success`, `router_fail`.

## Phase 2 Implementation (Top 3)

### 2.1 Proprioception for Policy Router

Files:
- `workspace/scripts/proprioception.py`
- `workspace/scripts/policy_router.py`
- `tests_unittest/test_router_proprioception.py`

Design:
- Added `ProprioceptiveSampler` with fixed-size rolling buffer (`maxlen=200`) and deterministic quantiles.
- Router measures end-to-end decision duration with monotonic clock and records `tokens_in`, success/failure, provider.
- Added optional `meta.proprioception` attachment gated by `OPENCLAW_ROUTER_PROPRIOCEPTION=1`.
- No contract break when flag is off; `meta` key is not added by proprioception path.
- Added `tacti_features_from_proprioception(snapshot)` adaptor and injects features into context only when flag is on.

Verification:
```text
$ python3 -m unittest -q tests_unittest/test_router_proprioception.py tests_unittest/test_policy_router_tacti_main_flow.py tests_unittest/test_policy_router_active_inference_hook.py
----------------------------------------------------------------------
Ran 6 tests in 0.015s

OK
```

### 2.2 Narrative Memory Distillation

Files:
- `workspace/scripts/narrative_distill.py`
- `workspace/scripts/run_narrative_distill.py`
- `workspace/scripts/nightly_build.sh`
- `tests_unittest/test_narrative_distill.py`

Design:
- Added deterministic distiller: `distill_episodes(episodes, max_items=50)`.
- Clusters episodes by token Jaccard threshold, then emits stable semantic facts:
  - `fact`, `entities`, `topics`, `support_count`, `source_ids`, `timestamp_utc`.
- Writer prefers HiveMind trails backend (semantic namespace in `meta`) and falls back to append-only JSONL.
- Added manual CLI runner and optional nightly hook under `OPENCLAW_NARRATIVE_DISTILL=1`.

Verification:
```text
$ python3 -m unittest -q tests_unittest/test_narrative_distill.py tests_unittest/test_tacti_cr_novel_10.py
----------------------------------------------------------------------
Ran 11 tests in 0.040s

OK
```

### 2.3 Witness Ledger

Files:
- `workspace/scripts/witness_ledger.py`
- `workspace/scripts/policy_router.py` (hook path)
- `tests_unittest/test_witness_ledger.py`

Design:
- Added append-only witness ledger with stable canonical JSON bytes and SHA-256 commitments.
- Chain format: `seq`, `timestamp_utc`, `prev_hash`, `hash`, `record`.
- Router hook is opt-in (`OPENCLAW_WITNESS_LEDGER=1`) and writes only minimal non-sensitive routing summary record.
- Router adds `witness_hash` in event detail and `result.meta` when enabled.

Verification:
```text
$ python3 -m unittest -q tests_unittest/test_witness_ledger.py tests_unittest/test_router_proprioception.py
----------------------------------------------------------------------
Ran 4 tests in 0.005s

OK
```

## Phase 3 Implementation (Scaffolds for Ideas 1,3,4,5,7,8,9)

Files:
- `workspace/tacti_cr/dream_consolidation.py`
- `workspace/hivemind/hivemind/trails.py`
- `workspace/tacti_cr/temporal.py`
- `workspace/hivemind/hivemind/peer_graph.py`
- `workspace/hivemind/hivemind/active_inference.py`
- `workspace/tacti_cr/semantic_immune.py`
- `workspace/tacti_cr/oscillatory_gating.py`
- `tests_unittest/test_evolution_scaffolds.py`
- `README.md`

Scaffolded behavior (all default off):
- Idea 1: `OPENCLAW_DREAM_PRUNE` with deterministic `prune_competing_clusters(...)`.
- Idea 3: `OPENCLAW_TRAIL_VALENCE` with damped valence signatures (`0.5^hops`).
- Idea 4: `OPENCLAW_SURPRISE_GATE` with cosine-distance surprise proxy and optional episodic write gate.
- Idea 5: `OPENCLAW_PEER_ANNEAL` with temperature-decayed churn probability.
- Idea 7: `OPENCLAW_COUNTERFACTUAL_REPLAY` with deterministic heuristic alternatives.
- Idea 8: `OPENCLAW_EPITOPE_CACHE` bounded LRU fingerprint cache for rapid reject path.
- Idea 9: `OPENCLAW_OSCILLATORY_GATING` deterministic phase scheduler.

Verification:
```text
$ python3 -m unittest -q tests_unittest/test_evolution_scaffolds.py tests_unittest/test_hivemind_peer_graph.py tests_unittest/test_hivemind_trails.py tests_unittest/test_hivemind_active_inference.py tests_unittest/test_tacti_cr_temporal.py tests_unittest/test_tacti_cr_novel_10.py
----------------------------------------------------------------------
Ran 29 tests in 0.530s

OK
```

## Phase 4 Verification Gates

```text
$ python3 -m unittest -q
----------------------------------------------------------------------
Ran 120 tests in 3.878s

OK

$ npm test --silent
...
OK 38 test group(s)
```

## Commits

```text
5d7ea43 feat(router): add proprioception sampler and optional meta hooks
2b36b3e feat(memory): add narrative distillation module and runner
4bd3530 feat(audit): add witness ledger hash-chain module and tests
43a13fa feat(evolution): add flag-gated scaffolds for ideas 1,3,4,5,7,8,9
```

## Flag Table

| Flag | Default | Effect |
|---|---:|---|
| OPENCLAW_ROUTER_PROPRIOCEPTION | 0 | Attach rolling router telemetry in `result.meta.proprioception` |
| OPENCLAW_NARRATIVE_DISTILL | 0 | Enable nightly episodic→semantic distillation run |
| OPENCLAW_WITNESS_LEDGER | 0 | Enable append-only witness hash-chain commits for router decisions |
| OPENCLAW_DREAM_PRUNE | 0 | Enable deterministic competing-cluster pruning |
| OPENCLAW_TRAIL_VALENCE | 0 | Persist damped trail valence signatures |
| OPENCLAW_SURPRISE_GATE | 0 | Gate episodic writes by surprise proxy |
| OPENCLAW_PEER_ANNEAL | 0 | Apply temperature schedule to peer churn |
| OPENCLAW_COUNTERFACTUAL_REPLAY | 0 | Generate deterministic counterfactual routing alternatives |
| OPENCLAW_EPITOPE_CACHE | 0 | Enable semantic-immune losing-claim fingerprint cache |
| OPENCLAW_OSCILLATORY_GATING | 0 | Enable phase-cycled maintenance gating |

## Known Limits / Follow-ups

- Witness ledger commit currently stores minimal routing summary record only; no cross-process lock is used.
- Narrative distillation currently uses token Jaccard fallback and does not require embedding infrastructure.
- `workspace/state/tacti_cr/events.jsonl` is a tracked runtime log and remained dirty in this worktree baseline; intentionally excluded from commits.
