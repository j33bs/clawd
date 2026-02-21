# Dali vLLM Duplicate Process Audit

- Audit file: workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md
- Host: Dali (Ubuntu)
- Start (UTC): 2026-02-21T20:44:11Z

## Problem Statement
Reported issue: duplicate vLLM/local-assistant processes appear to claim port 8001 and cause gateway instability (error id tg-mlws9pj6-002). This audit verifies whether duplication is current or stale, identifies the launcher path (systemd/cron/manual), applies a minimal singleton fix, and records rollback steps.

```bash
date -u
```

```text
Sat Feb 21 20:44:11 UTC 2026
```

```bash
uname -a
```

```text
Linux jeebs-Z490-AORUS-MASTER 6.17.0-14-generic #14~24.04.1-Ubuntu SMP PREEMPT_DYNAMIC Thu Jan 15 15:52:10 UTC 2 x86_64 x86_64 x86_64 GNU/Linux
```

```bash
git rev-parse HEAD
```

```text
01155d3c6f4f0a3881286c619fb9d0f7212fc0d7
```

```bash
systemctl --version | head -n 1
```

```text
systemd 255 (255.4-1ubuntu8.12)
```

```bash
python3 --version
```

```text
Python 3.12.3
```

```bash
node --version
```

```text
v22.22.0
```

```bash
set -euo pipefail
date -u

# What is listening on 8001?
ss -ltnp | sed -n '1,200p' | grep -E '(:8001)\b' || true

# Identify vLLM processes and their command lines
ps auxww | grep -E '[v]llm|openai\.api_server|api_server|local-assistant' || true

# Show process tree if available
command -v pstree >/dev/null && pstree -ap | grep -i -E 'vllm|api_server|8001' || true

# For each PID you find, capture start time and full cmdline
for pid in $(pgrep -f 'vllm|openai.api_server|api_server' || true); do
  echo "=== PID $pid ==="
  ps -p "$pid" -o pid,lstart,etime,cmd --no-headers || true
  tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true
  echo
done

# Confirm port ownership via /proc (more reliable than guesses)
for pid in $(pgrep -f 'vllm|openai.api_server|api_server' || true); do
  echo "=== PID $pid FD sockets (filtered) ==="
  ls -l "/proc/$pid/fd" 2>/dev/null | grep -E 'socket:' || true
done
```

```text
Sat Feb 21 20:44:40 UTC 2026
Cannot open netlink socket: Operation not permitted
LISTEN 0      0          127.0.0.1:8001       0.0.0.0:*          
jeebs       3285  1.5  3.1 11374464 1034396 ?    Ssl  06:35   0:08 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8
jeebs       3360  0.0  0.0  30968 12728 ?        S    06:35   0:00 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c from multiprocessing.resource_tracker import main;main(34)
jeebs      10054 93.9  2.9 9746316 980544 ?      Ssl  06:44   0:07 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8 --enable-auto-tool-choice --tool-call-parser hermes
jeebs      10111  0.3  0.0  30968 12780 ?        S    06:44   0:00 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c from multiprocessing.resource_tracker import main;main(34)
jeebs      10112  141  2.3 6595656 756252 ?      Rl   06:44   0:04 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=35, pipe_handle=37) --multiprocessing-fork
jeebs      10135  0.0  0.0  19020  3492 ?        Ss   06:44   0:00 /bin/bash -c set -eo pipefail AUDIT='workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md' PHASE1='/tmp/dali_phase1_cmd.sh' cat > "$PHASE1" <<'EOF' set -euo pipefail date -u  # What is listening on 8001? ss -ltnp | sed -n '1,200p' | grep -E '(:8001)\b' || true  # Identify vLLM processes and their command lines ps auxww | grep -E '[v]llm|openai\.api_server|api_server|local-assistant' || true  # Show process tree if available command -v pstree >/dev/null && pstree -ap | grep -i -E 'vllm|api_server|8001' || true  # For each PID you find, capture start time and full cmdline for pid in $(pgrep -f 'vllm|openai.api_server|api_server' || true); do   echo "=== PID $pid ==="   ps -p "$pid" -o pid,lstart,etime,cmd --no-headers || true   tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true   echo done  # Confirm port ownership via /proc (more reliable than guesses) for pid in $(pgrep -f 'vllm|openai.api_server|api_server' || true); do   echo "=== PID $pid FD sockets (filtered) ==="   ls -l "/proc/$pid/fd" 2>/dev/null | grep -E 'socket:' || true done EOF  {   echo '```bash'   cat "$PHASE1"   echo '```'   echo   echo '```text' } >> "$AUDIT"  bash "$PHASE1" >> "$AUDIT" 2>&1 || true  {   echo '```'   echo } >> "$AUDIT"  # classify based on current listeners and unique process names LISTEN_INFO=$(ss -ltnp | grep -E '(:8001)\b' || true) LINES=$(printf '%s\n' "$LISTEN_INFO" | sed '/^$/d' | wc -l | tr -d ' ') CLASS='C' if [ "$LINES" -ge 2 ]; then   CLASS='A' elif [ "$LINES" -eq 1 ]; then   CLASS='B' fi {   echo '## Phase 1 Classification'   echo   echo "- Classified case: **$CLASS**"   echo '- Legend: A=two distinct PIDs both bound to :8001, B=one bound with other process not bound/crash-loop, C=duplicate report stale/incorrect'   echo   echo '```text'   printf '%s\n' "$LISTEN_INFO"   echo '```'   echo } >> "$AUDIT"  printf '%s\n' "$CLASS"
jeebs      10144  0.0  0.0  18368  2160 ?        S    06:44   0:00 grep -E [v]llm|openai\.api_server|api_server|local-assistant
  |   |   |       |   |       |-grep,10146 -i -E vllm|api_server|8001
  |   |-python3.12,10054 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve/opt/models/qwen2_5_14b_instruct_awq
  |-vllm,3285 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve/opt/models/qwen2_5_14b_instruct_awq
  |   |-VLLM::EngineCor,3361
  |   |   |-{VLLM::EngineCor},3362
  |   |   |-{VLLM::EngineCor},3363
  |   |   |-{VLLM::EngineCor},3364
  |   |   |-{VLLM::EngineCor},3365
  |   |   |-{VLLM::EngineCor},3366
  |   |   |-{VLLM::EngineCor},3367
  |   |   |-{VLLM::EngineCor},3368
  |   |   |-{VLLM::EngineCor},3369
  |   |   |-{VLLM::EngineCor},3370
  |   |   |-{VLLM::EngineCor},3371
  |   |   |-{VLLM::EngineCor},3372
  |   |   |-{VLLM::EngineCor},3373
  |   |   |-{VLLM::EngineCor},3374
  |   |   |-{VLLM::EngineCor},3375
  |   |   |-{VLLM::EngineCor},3376
  |   |   |-{VLLM::EngineCor},3377
  |   |   |-{VLLM::EngineCor},3378
  |   |   |-{VLLM::EngineCor},3379
  |   |   |-{VLLM::EngineCor},3380
  |   |   |-{VLLM::EngineCor},3383
  |   |   |-{VLLM::EngineCor},3432
  |   |   |-{VLLM::EngineCor},3433
  |   |   |-{VLLM::EngineCor},3434
  |   |   |-{VLLM::EngineCor},3435
  |   |   |-{VLLM::EngineCor},3436
  |   |   |-{VLLM::EngineCor},3437
  |   |   |-{VLLM::EngineCor},3438
  |   |   |-{VLLM::EngineCor},3439
  |   |   |-{VLLM::EngineCor},3440
  |   |   |-{VLLM::EngineCor},3441
  |   |   |-{VLLM::EngineCor},3442
  |   |   |-{VLLM::EngineCor},3443
  |   |   |-{VLLM::EngineCor},3444
  |   |   |-{VLLM::EngineCor},3445
  |   |   |-{VLLM::EngineCor},3446
  |   |   |-{VLLM::EngineCor},3447
  |   |   |-{VLLM::EngineCor},3448
  |   |   |-{VLLM::EngineCor},3449
  |   |   |-{VLLM::EngineCor},3450
  |   |   |-{VLLM::EngineCor},3457
  |   |   |-{VLLM::EngineCor},3458
  |   |   |-{VLLM::EngineCor},3459
  |   |   |-{VLLM::EngineCor},3460
  |   |   |-{VLLM::EngineCor},3461
  |   |   |-{VLLM::EngineCor},3462
  |   |   |-{VLLM::EngineCor},3463
  |   |   |-{VLLM::EngineCor},3464
  |   |   |-{VLLM::EngineCor},3465
  |   |   |-{VLLM::EngineCor},3466
  |   |   |-{VLLM::EngineCor},3467
  |   |   |-{VLLM::EngineCor},3468
  |   |   |-{VLLM::EngineCor},3469
  |   |   |-{VLLM::EngineCor},3470
  |   |   |-{VLLM::EngineCor},3471
  |   |   |-{VLLM::EngineCor},3472
  |   |   |-{VLLM::EngineCor},3473
  |   |   |-{VLLM::EngineCor},3474
  |   |   |-{VLLM::EngineCor},3475
  |   |   |-{VLLM::EngineCor},3476
  |   |   |-{VLLM::EngineCor},3477
  |   |   |-{VLLM::EngineCor},3478
  |   |   |-{VLLM::EngineCor},3479
  |   |   |-{VLLM::EngineCor},3480
  |   |   |-{VLLM::EngineCor},3481
  |   |   |-{VLLM::EngineCor},3482
  |   |   |-{VLLM::EngineCor},3483
  |   |   |-{VLLM::EngineCor},3484
  |   |   |-{VLLM::EngineCor},3485
  |   |   |-{VLLM::EngineCor},3486
  |   |   |-{VLLM::EngineCor},3487
  |   |   |-{VLLM::EngineCor},3488
  |   |   |-{VLLM::EngineCor},3489
  |   |   |-{VLLM::EngineCor},3490
  |   |   |-{VLLM::EngineCor},3491
  |   |   |-{VLLM::EngineCor},3492
  |   |   |-{VLLM::EngineCor},3493
  |   |   |-{VLLM::EngineCor},3494
  |   |   |-{VLLM::EngineCor},3495
  |   |   |-{VLLM::EngineCor},3496
  |   |   |-{VLLM::EngineCor},3497
  |   |   |-{VLLM::EngineCor},3498
  |   |   |-{VLLM::EngineCor},3499
  |   |   |-{VLLM::EngineCor},3500
  |   |   |-{VLLM::EngineCor},3501
  |   |   |-{VLLM::EngineCor},3502
  |   |   |-{VLLM::EngineCor},3535
  |   |   |-{VLLM::EngineCor},3673
  |   |   |-{VLLM::EngineCor},3790
  |   |   |-{VLLM::EngineCor},3791
  |   |   |-{VLLM::EngineCor},3792
  |   |   |-{VLLM::EngineCor},3793
  |   |   |-{VLLM::EngineCor},3794
  |   |   `-{VLLM::EngineCor},3795
  |   |-{vllm},3292
  |   |-{vllm},3293
  |   |-{vllm},3294
  |   |-{vllm},3295
  |   |-{vllm},3296
  |   |-{vllm},3297
  |   |-{vllm},3298
  |   |-{vllm},3299
  |   |-{vllm},3300
  |   |-{vllm},3301
  |   |-{vllm},3302
  |   |-{vllm},3303
  |   |-{vllm},3304
  |   |-{vllm},3305
  |   |-{vllm},3306
  |   |-{vllm},3307
  |   |-{vllm},3308
  |   |-{vllm},3309
  |   |-{vllm},3310
  |   |-{vllm},3311
  |   |-{vllm},3334
  |   |-{vllm},3335
  |   |-{vllm},3336
  |   |-{vllm},3337
  |   |-{vllm},3338
  |   |-{vllm},3339
  |   |-{vllm},3340
  |   |-{vllm},3341
  |   |-{vllm},3342
  |   |-{vllm},3343
  |   |-{vllm},3344
  |   |-{vllm},3345
  |   |-{vllm},3346
  |   |-{vllm},3347
  |   |-{vllm},3348
  |   |-{vllm},3349
  |   |-{vllm},3350
  |   |-{vllm},3351
  |   |-{vllm},3352
  |   |-{vllm},3354
  |   |-{vllm},3796
  |   |-{vllm},3797
  |   |-{vllm},3798
  |   |-{vllm},3799
  |   |-{vllm},3801
  |   |-{vllm},3802
  |   |-{vllm},3803
  |   |-{vllm},3804
  |   |-{vllm},3805
  |   |-{vllm},3806
  |   |-{vllm},3807
  |   |-{vllm},3808
  |   |-{vllm},3809
  |   |-{vllm},3810
  |   |-{vllm},3811
  |   |-{vllm},3812
  |   |-{vllm},3813
  |   |-{vllm},3814
  |   |-{vllm},3815
  |   |-{vllm},3816
  |   |-{vllm},3817
  |   |-{vllm},3818
  |   |-{vllm},3819
  |   |-{vllm},3820
  |   `-{vllm},3821
=== PID 3285 ===
   3285 Sun Feb 22 06:35:31 2026       09:09 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8
/home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8 
=== PID 3360 ===
   3360 Sun Feb 22 06:35:36 2026       09:04 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c from multiprocessing.resource_tracker import main;main(34)
/home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c from multiprocessing.resource_tracker import main;main(34) 
=== PID 10054 ===
  10054 Sun Feb 22 06:44:32 2026       00:08 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8 --enable-auto-tool-choice --tool-call-parser hermes
/home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8 --enable-auto-tool-choice --tool-call-parser hermes 
=== PID 10111 ===
  10111 Sun Feb 22 06:44:37 2026       00:03 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c from multiprocessing.resource_tracker import main;main(34)
/home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c from multiprocessing.resource_tracker import main;main(34) 
=== PID 10112 ===
  10112 Sun Feb 22 06:44:37 2026       00:03 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=35, pipe_handle=37) --multiprocessing-fork
/home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=35, pipe_handle=37) --multiprocessing-fork 
=== PID 10135 ===
  10135 Sun Feb 22 06:44:40 2026       00:00 /bin/bash -c set -eo pipefail AUDIT='workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md' PHASE1='/tmp/dali_phase1_cmd.sh' cat > "$PHASE1" <<'EOF' set -euo pipefail date -u  # What is listening on 8001? ss -ltnp | sed -n '1,200p' | grep -E '(:8001)\b' || true  # Identify vLLM processes and their command lines ps auxww | grep -E '[v]llm|openai\.api_server|api_server|local-assistant' || true  # Show process tree if available command -v pstree >/dev/null && pstree -ap | grep -i -E 'vllm|api_server|8001' || true  # For each PID you find, capture start time and full cmdline for pid in $(pgrep -f 'vllm|openai.api_server|api_server' || true); do   echo "=== PID $pid ==="   ps -p "$pid" -o pid,lstart,etime,cmd --no-headers || true   tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true   echo done  # Confirm port ownership via /proc (more reliable than guesses) for pid in $(pgrep -f 'vllm|openai.api_server|api_server' || true); do   echo "=== PID $pid FD sockets (filtered) ==="   ls -l "/proc/$pid/fd" 2>/dev/null | grep -E 'socket:' || true done EOF  {   echo '```bash'   cat "$PHASE1"   echo '```'   echo   echo '```text' } >> "$AUDIT"  bash "$PHASE1" >> "$AUDIT" 2>&1 || true  {   echo '```'   echo } >> "$AUDIT"  # classify based on current listeners and unique process names LISTEN_INFO=$(ss -ltnp | grep -E '(:8001)\b' || true) LINES=$(printf '%s\n' "$LISTEN_INFO" | sed '/^$/d' | wc -l | tr -d ' ') CLASS='C' if [ "$LINES" -ge 2 ]; then   CLASS='A' elif [ "$LINES" -eq 1 ]; then   CLASS='B' fi {   echo '## Phase 1 Classification'   echo   echo "- Classified case: **$CLASS**"   echo '- Legend: A=two distinct PIDs both bound to :8001, B=one bound with other process not bound/crash-loop, C=duplicate report stale/incorrect'   echo   echo '```text'   printf '%s\n' "$LISTEN_INFO"   echo '```'   echo } >> "$AUDIT"  printf '%s\n' "$CLASS"
/bin/bash -c set -eo pipefail
AUDIT='workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md'
PHASE1='/tmp/dali_phase1_cmd.sh'
cat > "$PHASE1" <<'EOF'
set -euo pipefail
date -u

# What is listening on 8001?
ss -ltnp | sed -n '1,200p' | grep -E '(:8001)\b' || true

# Identify vLLM processes and their command lines
ps auxww | grep -E '[v]llm|openai\.api_server|api_server|local-assistant' || true

# Show process tree if available
command -v pstree >/dev/null && pstree -ap | grep -i -E 'vllm|api_server|8001' || true

# For each PID you find, capture start time and full cmdline
for pid in $(pgrep -f 'vllm|openai.api_server|api_server' || true); do
  echo "=== PID $pid ==="
  ps -p "$pid" -o pid,lstart,etime,cmd --no-headers || true
  tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true
  echo
done

# Confirm port ownership via /proc (more reliable than guesses)
for pid in $(pgrep -f 'vllm|openai.api_server|api_server' || true); do
  echo "=== PID $pid FD sockets (filtered) ==="
  ls -l "/proc/$pid/fd" 2>/dev/null | grep -E 'socket:' || true
done
EOF

{
  echo '```bash'
  cat "$PHASE1"
  echo '```'
  echo
  echo '```text'
} >> "$AUDIT"

bash "$PHASE1" >> "$AUDIT" 2>&1 || true

{
  echo '```'
  echo
} >> "$AUDIT"

# classify based on current listeners and unique process names
LISTEN_INFO=$(ss -ltnp | grep -E '(:8001)\b' || true)
LINES=$(printf '%s\n' "$LISTEN_INFO" | sed '/^$/d' | wc -l | tr -d ' ')
CLASS='C'
if [ "$LINES" -ge 2 ]; then
  CLASS='A'
elif [ "$LINES" -eq 1 ]; then
  CLASS='B'
fi
{
  echo '## Phase 1 Classification'
  echo
  echo "- Classified case: **$CLASS**"
  echo '- Legend: A=two distinct PIDs both bound to :8001, B=one bound with other process not bound/crash-loop, C=duplicate report stale/incorrect'
  echo
  echo '```text'
  printf '%s\n' "$LISTEN_INFO"
  echo '```'
  echo
} >> "$AUDIT"

printf '%s\n' "$CLASS" 
=== PID 3285 FD sockets (filtered) ===
=== PID 3360 FD sockets (filtered) ===
=== PID 10054 FD sockets (filtered) ===
=== PID 10111 FD sockets (filtered) ===
=== PID 10112 FD sockets (filtered) ===
=== PID 10135 FD sockets (filtered) ===
```

## Phase 1 Classification

- Classified case: **B**
- Legend: A=two distinct PIDs both bound to :8001, B=one bound with other process not bound/crash-loop, C=duplicate report stale/incorrect

```text
LISTEN 0      0          127.0.0.1:8001       0.0.0.0:*          
```

### Phase 1 (Escalated for socket/process visibility)

```bash
set -euo pipefail
date -u

# What is listening on 8001?
ss -ltnp | sed -n '1,200p' | grep -E '(:8001)\b' || true

# Identify vLLM processes and their command lines
ps auxww | grep -E '[v]llm|openai\.api_server|api_server|local-assistant' || true

# Show process tree if available
command -v pstree >/dev/null && pstree -ap | grep -i -E 'vllm|api_server|8001' || true

# For each PID you find, capture start time and full cmdline
for pid in $(pgrep -f 'vllm|openai.api_server|api_server' || true); do
  echo "=== PID $pid ==="
  ps -p "$pid" -o pid,lstart,etime,cmd --no-headers || true
  tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true
  echo
done

# Confirm port ownership via /proc (more reliable than guesses)
for pid in $(pgrep -f 'vllm|openai.api_server|api_server' || true); do
  echo "=== PID $pid FD sockets (filtered) ==="
  ls -l "/proc/$pid/fd" 2>/dev/null | grep -E 'socket:' || true
done
```

```text
Sat Feb 21 20:51:17 UTC 2026
LISTEN 0      2048       127.0.0.1:8001       0.0.0.0:*    users:(("vllm",pid=3285,fd=25))           
jeebs       3285  0.9  3.1 11374464 1034400 ?    Ssl  06:35   0:08 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8
jeebs       3360  0.0  0.0  30968 12728 ?        S    06:35   0:00 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c from multiprocessing.resource_tracker import main;main(34)
jeebs      13724  209  1.8 5642824 595708 ?      Rsl  06:51   0:02 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8 --enable-auto-tool-choice --tool-call-parser hermes
jeebs      13748  0.0  0.0  19020  3580 ?        Ss   06:51   0:00 /bin/bash -c set -euo pipefail AUDIT='workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md' PHASE1='/tmp/dali_phase1_cmd_escalated.sh' cat > "$PHASE1" <<'EOF' set -euo pipefail date -u  # What is listening on 8001? ss -ltnp | sed -n '1,200p' | grep -E '(:8001)\b' || true  # Identify vLLM processes and their command lines ps auxww | grep -E '[v]llm|openai\.api_server|api_server|local-assistant' || true  # Show process tree if available command -v pstree >/dev/null && pstree -ap | grep -i -E 'vllm|api_server|8001' || true  # For each PID you find, capture start time and full cmdline for pid in $(pgrep -f 'vllm|openai.api_server|api_server' || true); do   echo "=== PID $pid ==="   ps -p "$pid" -o pid,lstart,etime,cmd --no-headers || true   tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true   echo done  # Confirm port ownership via /proc (more reliable than guesses) for pid in $(pgrep -f 'vllm|openai.api_server|api_server' || true); do   echo "=== PID $pid FD sockets (filtered) ==="   ls -l "/proc/$pid/fd" 2>/dev/null | grep -E 'socket:' || true done EOF  {   echo '### Phase 1 (Escalated for socket/process visibility)'   echo   echo '```bash'   cat "$PHASE1"   echo '```'   echo   echo '```text' } >> "$AUDIT"  bash "$PHASE1" >> "$AUDIT" 2>&1 || true  {   echo '```'   echo } >> "$AUDIT"  LISTEN_INFO=$(ss -ltnp | grep -E '(:8001)\b' || true) LINES=$(printf '%s\n' "$LISTEN_INFO" | sed '/^$/d' | wc -l | tr -d ' ') CLASS='C' if [ "$LINES" -ge 2 ]; then   CLASS='A' elif [ "$LINES" -eq 1 ]; then   CLASS='B' fi {   echo '## Phase 1 Classification (Post-Escalation)'   echo   echo "- Classified case: **$CLASS**"   echo '- Legend: A=two distinct PIDs both bound to :8001, B=one bound with other process not bound/crash-loop, C=duplicate report stale/incorrect'   echo   echo '```text'   printf '%s\n' "$LISTEN_INFO"   echo '```'   echo } >> "$AUDIT"  echo "$CLASS"
jeebs      13761  0.0  0.0  18368  2156 ?        S    06:51   0:00 grep -E [v]llm|openai\.api_server|api_server|local-assistant
  |   |   |       |   |       |-grep,13763 -i -E vllm|api_server|8001
  |   |-python3.12,13724 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve/opt/models/qwen2_5_14b_instruct_awq
  |-vllm,3285 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve/opt/models/qwen2_5_14b_instruct_awq
  |   |-VLLM::EngineCor,3361
  |   |   |-{VLLM::EngineCor},3362
  |   |   |-{VLLM::EngineCor},3363
  |   |   |-{VLLM::EngineCor},3364
  |   |   |-{VLLM::EngineCor},3365
  |   |   |-{VLLM::EngineCor},3366
  |   |   |-{VLLM::EngineCor},3367
  |   |   |-{VLLM::EngineCor},3368
  |   |   |-{VLLM::EngineCor},3369
  |   |   |-{VLLM::EngineCor},3370
  |   |   |-{VLLM::EngineCor},3371
  |   |   |-{VLLM::EngineCor},3372
  |   |   |-{VLLM::EngineCor},3373
  |   |   |-{VLLM::EngineCor},3374
  |   |   |-{VLLM::EngineCor},3375
  |   |   |-{VLLM::EngineCor},3376
  |   |   |-{VLLM::EngineCor},3377
  |   |   |-{VLLM::EngineCor},3378
  |   |   |-{VLLM::EngineCor},3379
  |   |   |-{VLLM::EngineCor},3380
  |   |   |-{VLLM::EngineCor},3383
  |   |   |-{VLLM::EngineCor},3432
  |   |   |-{VLLM::EngineCor},3433
  |   |   |-{VLLM::EngineCor},3434
  |   |   |-{VLLM::EngineCor},3435
  |   |   |-{VLLM::EngineCor},3436
  |   |   |-{VLLM::EngineCor},3437
  |   |   |-{VLLM::EngineCor},3438
  |   |   |-{VLLM::EngineCor},3439
  |   |   |-{VLLM::EngineCor},3440
  |   |   |-{VLLM::EngineCor},3441
  |   |   |-{VLLM::EngineCor},3442
  |   |   |-{VLLM::EngineCor},3443
  |   |   |-{VLLM::EngineCor},3444
  |   |   |-{VLLM::EngineCor},3445
  |   |   |-{VLLM::EngineCor},3446
  |   |   |-{VLLM::EngineCor},3447
  |   |   |-{VLLM::EngineCor},3448
  |   |   |-{VLLM::EngineCor},3449
  |   |   |-{VLLM::EngineCor},3450
  |   |   |-{VLLM::EngineCor},3457
  |   |   |-{VLLM::EngineCor},3458
  |   |   |-{VLLM::EngineCor},3459
  |   |   |-{VLLM::EngineCor},3460
  |   |   |-{VLLM::EngineCor},3461
  |   |   |-{VLLM::EngineCor},3462
  |   |   |-{VLLM::EngineCor},3463
  |   |   |-{VLLM::EngineCor},3464
  |   |   |-{VLLM::EngineCor},3465
  |   |   |-{VLLM::EngineCor},3466
  |   |   |-{VLLM::EngineCor},3467
  |   |   |-{VLLM::EngineCor},3468
  |   |   |-{VLLM::EngineCor},3469
  |   |   |-{VLLM::EngineCor},3470
  |   |   |-{VLLM::EngineCor},3471
  |   |   |-{VLLM::EngineCor},3472
  |   |   |-{VLLM::EngineCor},3473
  |   |   |-{VLLM::EngineCor},3474
  |   |   |-{VLLM::EngineCor},3475
  |   |   |-{VLLM::EngineCor},3476
  |   |   |-{VLLM::EngineCor},3477
  |   |   |-{VLLM::EngineCor},3478
  |   |   |-{VLLM::EngineCor},3479
  |   |   |-{VLLM::EngineCor},3480
  |   |   |-{VLLM::EngineCor},3481
  |   |   |-{VLLM::EngineCor},3482
  |   |   |-{VLLM::EngineCor},3483
  |   |   |-{VLLM::EngineCor},3484
  |   |   |-{VLLM::EngineCor},3485
  |   |   |-{VLLM::EngineCor},3486
  |   |   |-{VLLM::EngineCor},3487
  |   |   |-{VLLM::EngineCor},3488
  |   |   |-{VLLM::EngineCor},3489
  |   |   |-{VLLM::EngineCor},3490
  |   |   |-{VLLM::EngineCor},3491
  |   |   |-{VLLM::EngineCor},3492
  |   |   |-{VLLM::EngineCor},3493
  |   |   |-{VLLM::EngineCor},3494
  |   |   |-{VLLM::EngineCor},3495
  |   |   |-{VLLM::EngineCor},3496
  |   |   |-{VLLM::EngineCor},3497
  |   |   |-{VLLM::EngineCor},3498
  |   |   |-{VLLM::EngineCor},3499
  |   |   |-{VLLM::EngineCor},3500
  |   |   |-{VLLM::EngineCor},3501
  |   |   |-{VLLM::EngineCor},3502
  |   |   |-{VLLM::EngineCor},3535
  |   |   |-{VLLM::EngineCor},3673
  |   |   |-{VLLM::EngineCor},3790
  |   |   |-{VLLM::EngineCor},3791
  |   |   |-{VLLM::EngineCor},3792
  |   |   |-{VLLM::EngineCor},3793
  |   |   |-{VLLM::EngineCor},3794
  |   |   `-{VLLM::EngineCor},3795
  |   |-{vllm},3292
  |   |-{vllm},3293
  |   |-{vllm},3294
  |   |-{vllm},3295
  |   |-{vllm},3296
  |   |-{vllm},3297
  |   |-{vllm},3298
  |   |-{vllm},3299
  |   |-{vllm},3300
  |   |-{vllm},3301
  |   |-{vllm},3302
  |   |-{vllm},3303
  |   |-{vllm},3304
  |   |-{vllm},3305
  |   |-{vllm},3306
  |   |-{vllm},3307
  |   |-{vllm},3308
  |   |-{vllm},3309
  |   |-{vllm},3310
  |   |-{vllm},3311
  |   |-{vllm},3334
  |   |-{vllm},3335
  |   |-{vllm},3336
  |   |-{vllm},3337
  |   |-{vllm},3338
  |   |-{vllm},3339
  |   |-{vllm},3340
  |   |-{vllm},3341
  |   |-{vllm},3342
  |   |-{vllm},3343
  |   |-{vllm},3344
  |   |-{vllm},3345
  |   |-{vllm},3346
  |   |-{vllm},3347
  |   |-{vllm},3348
  |   |-{vllm},3349
  |   |-{vllm},3350
  |   |-{vllm},3351
  |   |-{vllm},3352
  |   |-{vllm},3354
  |   |-{vllm},3796
  |   |-{vllm},3797
  |   |-{vllm},3798
  |   |-{vllm},3799
  |   |-{vllm},3801
  |   |-{vllm},3802
  |   |-{vllm},3803
  |   |-{vllm},3804
  |   |-{vllm},3805
  |   |-{vllm},3806
  |   |-{vllm},3807
  |   |-{vllm},3808
  |   |-{vllm},3809
  |   |-{vllm},3810
  |   |-{vllm},3811
  |   |-{vllm},3812
  |   |-{vllm},3813
  |   |-{vllm},3814
  |   |-{vllm},3815
  |   |-{vllm},3816
  |   |-{vllm},3817
  |   |-{vllm},3818
  |   |-{vllm},3819
  |   |-{vllm},3820
  |   `-{vllm},3821
=== PID 3285 ===
   3285 Sun Feb 22 06:35:31 2026       15:46 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8
/home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8 
=== PID 3360 ===
   3360 Sun Feb 22 06:35:36 2026       15:41 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c from multiprocessing.resource_tracker import main;main(34)
/home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c from multiprocessing.resource_tracker import main;main(34) 
=== PID 13724 ===
  13724 Sun Feb 22 06:51:16 2026       00:01 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8 --enable-auto-tool-choice --tool-call-parser hermes
/home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8 --enable-auto-tool-choice --tool-call-parser hermes 
=== PID 13748 ===
  13748 Sun Feb 22 06:51:17 2026       00:00 /bin/bash -c set -euo pipefail AUDIT='workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md' PHASE1='/tmp/dali_phase1_cmd_escalated.sh' cat > "$PHASE1" <<'EOF' set -euo pipefail date -u  # What is listening on 8001? ss -ltnp | sed -n '1,200p' | grep -E '(:8001)\b' || true  # Identify vLLM processes and their command lines ps auxww | grep -E '[v]llm|openai\.api_server|api_server|local-assistant' || true  # Show process tree if available command -v pstree >/dev/null && pstree -ap | grep -i -E 'vllm|api_server|8001' || true  # For each PID you find, capture start time and full cmdline for pid in $(pgrep -f 'vllm|openai.api_server|api_server' || true); do   echo "=== PID $pid ==="   ps -p "$pid" -o pid,lstart,etime,cmd --no-headers || true   tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true   echo done  # Confirm port ownership via /proc (more reliable than guesses) for pid in $(pgrep -f 'vllm|openai.api_server|api_server' || true); do   echo "=== PID $pid FD sockets (filtered) ==="   ls -l "/proc/$pid/fd" 2>/dev/null | grep -E 'socket:' || true done EOF  {   echo '### Phase 1 (Escalated for socket/process visibility)'   echo   echo '```bash'   cat "$PHASE1"   echo '```'   echo   echo '```text' } >> "$AUDIT"  bash "$PHASE1" >> "$AUDIT" 2>&1 || true  {   echo '```'   echo } >> "$AUDIT"  LISTEN_INFO=$(ss -ltnp | grep -E '(:8001)\b' || true) LINES=$(printf '%s\n' "$LISTEN_INFO" | sed '/^$/d' | wc -l | tr -d ' ') CLASS='C' if [ "$LINES" -ge 2 ]; then   CLASS='A' elif [ "$LINES" -eq 1 ]; then   CLASS='B' fi {   echo '## Phase 1 Classification (Post-Escalation)'   echo   echo "- Classified case: **$CLASS**"   echo '- Legend: A=two distinct PIDs both bound to :8001, B=one bound with other process not bound/crash-loop, C=duplicate report stale/incorrect'   echo   echo '```text'   printf '%s\n' "$LISTEN_INFO"   echo '```'   echo } >> "$AUDIT"  echo "$CLASS"
/bin/bash -c set -euo pipefail
AUDIT='workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md'
PHASE1='/tmp/dali_phase1_cmd_escalated.sh'
cat > "$PHASE1" <<'EOF'
set -euo pipefail
date -u

# What is listening on 8001?
ss -ltnp | sed -n '1,200p' | grep -E '(:8001)\b' || true

# Identify vLLM processes and their command lines
ps auxww | grep -E '[v]llm|openai\.api_server|api_server|local-assistant' || true

# Show process tree if available
command -v pstree >/dev/null && pstree -ap | grep -i -E 'vllm|api_server|8001' || true

# For each PID you find, capture start time and full cmdline
for pid in $(pgrep -f 'vllm|openai.api_server|api_server' || true); do
  echo "=== PID $pid ==="
  ps -p "$pid" -o pid,lstart,etime,cmd --no-headers || true
  tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true
  echo
done

# Confirm port ownership via /proc (more reliable than guesses)
for pid in $(pgrep -f 'vllm|openai.api_server|api_server' || true); do
  echo "=== PID $pid FD sockets (filtered) ==="
  ls -l "/proc/$pid/fd" 2>/dev/null | grep -E 'socket:' || true
done
EOF

{
  echo '### Phase 1 (Escalated for socket/process visibility)'
  echo
  echo '```bash'
  cat "$PHASE1"
  echo '```'
  echo
  echo '```text'
} >> "$AUDIT"

bash "$PHASE1" >> "$AUDIT" 2>&1 || true

{
  echo '```'
  echo
} >> "$AUDIT"

LISTEN_INFO=$(ss -ltnp | grep -E '(:8001)\b' || true)
LINES=$(printf '%s\n' "$LISTEN_INFO" | sed '/^$/d' | wc -l | tr -d ' ')
CLASS='C'
if [ "$LINES" -ge 2 ]; then
  CLASS='A'
elif [ "$LINES" -eq 1 ]; then
  CLASS='B'
fi
{
  echo '## Phase 1 Classification (Post-Escalation)'
  echo
  echo "- Classified case: **$CLASS**"
  echo '- Legend: A=two distinct PIDs both bound to :8001, B=one bound with other process not bound/crash-loop, C=duplicate report stale/incorrect'
  echo
  echo '```text'
  printf '%s\n' "$LISTEN_INFO"
  echo '```'
  echo
} >> "$AUDIT"

echo "$CLASS" 
=== PID 3285 FD sockets (filtered) ===
lrwx------ 1 jeebs jeebs 64 Feb 22 06:35 1 -> socket:[11119]
lrwx------ 1 jeebs jeebs 64 Feb 22 06:35 2 -> socket:[11119]
lrwx------ 1 jeebs jeebs 64 Feb 22 06:35 23 -> socket:[21105]
lrwx------ 1 jeebs jeebs 64 Feb 22 06:35 24 -> socket:[21106]
lrwx------ 1 jeebs jeebs 64 Feb 22 06:35 25 -> socket:[21107]
lrwx------ 1 jeebs jeebs 64 Feb 22 06:35 36 -> socket:[11145]
lrwx------ 1 jeebs jeebs 64 Feb 22 06:44 39 -> socket:[11146]
lrwx------ 1 jeebs jeebs 64 Feb 22 06:44 40 -> socket:[21282]
lrwx------ 1 jeebs jeebs 64 Feb 22 06:44 41 -> socket:[25509]
=== PID 3360 FD sockets (filtered) ===
lrwx------ 1 jeebs jeebs 64 Feb 22 06:35 1 -> socket:[11119]
lrwx------ 1 jeebs jeebs 64 Feb 22 06:35 2 -> socket:[11119]
=== PID 13724 FD sockets (filtered) ===
lrwx------ 1 jeebs jeebs 64 Feb 22 06:51 1 -> socket:[40467]
lrwx------ 1 jeebs jeebs 64 Feb 22 06:51 2 -> socket:[40467]
=== PID 13748 FD sockets (filtered) ===
```

## Phase 1 Classification (Post-Escalation)

- Classified case: **B**
- Legend: A=two distinct PIDs both bound to :8001, B=one bound with other process not bound/crash-loop, C=duplicate report stale/incorrect

```text
LISTEN 0      2048       127.0.0.1:8001       0.0.0.0:*    users:(("vllm",pid=3285,fd=25))           
```

## Phase 2 Launcher Attribution

```bash
# system services
systemctl list-units --type=service --all | grep -i -E 'openclaw|vllm|gateway|llm|local-assistant' || true
systemctl status openclaw-gateway.service --no-pager || true
systemctl status vllm.service --no-pager || true

# user services
systemctl --user list-units --type=service --all | grep -i -E 'openclaw|vllm|gateway|llm|local-assistant' || true
systemctl --user status openclaw-gateway.service --no-pager || true
systemctl --user status vllm.service --no-pager || true

# show unit definitions if present
systemctl cat openclaw-gateway.service 2>/dev/null || true
systemctl cat vllm.service 2>/dev/null || true
systemctl --user cat openclaw-gateway.service 2>/dev/null || true
systemctl --user cat vllm.service 2>/dev/null || true

# recent logs
journalctl -u openclaw-gateway.service -n 200 --no-pager || true
journalctl --user -u openclaw-gateway.service -n 200 --no-pager || true
journalctl -u vllm.service -n 200 --no-pager || true
journalctl --user -u vllm.service -n 200 --no-pager || true

# system cron
ls -la /etc/cron.* /etc/crontab 2>/dev/null || true
grep -RIn --color=never -E 'python-env-audit|openclaw|vllm|8001|local-assistant' /etc/cron* /etc/crontab 2>/dev/null || true

# user crontab
crontab -l 2>/dev/null || true

# systemd timers (system + user)
systemctl list-timers --all | sed -n '1,200p'
systemctl --user list-timers --all | sed -n '1,200p'
systemctl list-timers --all | grep -i -E 'openclaw|audit|python|vllm|llm' || true
systemctl --user list-timers --all | grep -i -E 'openclaw|audit|python|vllm|llm' || true
```

```text
  vllm-assistant.service                                loaded    active   running vLLM OpenAI Server (assistant)
Unit openclaw-gateway.service could not be found.
Unit vllm.service could not be found.
  openclaw-gateway.service                                         loaded    active   running OpenClaw Gateway (v2026.2.19-2)
  openclaw-vllm.service                                            loaded    active   running OpenClaw local vLLM server
● openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2)
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-gateway.service; enabled; preset: enabled)
    Drop-In: /home/jeebs/.config/systemd/user/openclaw-gateway.service.d
             └─10-provider-lock.conf, override.conf
     Active: active (running) since Sun 2026-02-22 06:34:42 AEST; 16min ago
   Main PID: 1682 (openclaw-gatewa)
      Tasks: 11 (limit: 38169)
     Memory: 829.5M (peak: 1.8G)
        CPU: 40.593s
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/openclaw-gateway.service
             └─1682 openclaw-gateway

Feb 22 06:39:38 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:39:38.190Z [telegram] telegram_handler_finally chatId=8159253715 messageId=518
Feb 22 06:39:38 jeebs-Z490-AORUS-MASTER node[1682]: {"event":"telegram_handler_failed","correlation_id":"tg-mlws8eku-001","update_id":518,"stage":"pipeline","err_class":"Error","err_message":"telegram handler timed out after 25000ms"}
Feb 22 06:39:38 jeebs-Z490-AORUS-MASTER node[1682]: {"event":"telegram_deadletter_write_failed","error":"TypeError: fs$1.mkdirSync is not a function"}
Feb 22 06:39:38 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:39:38.194Z [telegram] handler failed (correlation_id=tg-mlws8eku-001, stage=pipeline): telegram handler timed out after 25000ms
Feb 22 06:40:39 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:40:39.042Z [telegram] telegram_handler_finally chatId=8159253715 messageId=521
Feb 22 06:40:39 jeebs-Z490-AORUS-MASTER node[1682]: {"event":"telegram_handler_failed","correlation_id":"tg-mlws9pj6-002","update_id":521,"stage":"pipeline","err_class":"Error","err_message":"telegram handler timed out after 25000ms"}
Feb 22 06:40:39 jeebs-Z490-AORUS-MASTER node[1682]: {"event":"telegram_deadletter_write_failed","error":"TypeError: fs$1.mkdirSync is not a function"}
Feb 22 06:40:39 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:40:39.045Z [telegram] handler failed (correlation_id=tg-mlws9pj6-002, stage=pipeline): telegram handler timed out after 25000ms
Feb 22 06:40:40 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:40:40.452Z [telegram] telegram_handler_finally chatId=8159253715 messageId=522
Feb 22 06:40:51 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:40:51.796Z [telegram] telegram_handler_finally chatId=8159253715 messageId=524
Unit vllm.service could not be found.
# /home/jeebs/.config/systemd/user/openclaw-gateway.service
[Unit]
Description=OpenClaw Gateway (v2026.2.19-2)
After=network-online.target
Wants=network-online.target

[Service]
ExecStart="/usr/bin/node" "/usr/lib/node_modules/openclaw/dist/index.js" gateway --port 18789
Restart=always
RestartSec=5
KillMode=process
Environment="HOME=/home/jeebs"
Environment=TMPDIR=/tmp
Environment="PATH=/home/jeebs/.local/bin:/home/jeebs/.npm-global/bin:/home/jeebs/bin:/home/jeebs/.volta/bin:/home/jeebs/.asdf/shims:/home/jeebs/.bun/bin:/home/jeebs/.nvm/current/bin:/home/jeebs/.fnm/current/bin:/home/jeebs/.local/share/pnpm:/usr/local/bin:/usr/bin:/bin"
Environment=OPENCLAW_GATEWAY_PORT=18789
Environment=OPENCLAW_GATEWAY_TOKEN=4d6f7b84b1236e250ff79def5c11727669c0de5132793bda
Environment="OPENCLAW_SYSTEMD_UNIT=openclaw-gateway.service"
Environment=OPENCLAW_SERVICE_MARKER=openclaw
Environment=OPENCLAW_SERVICE_KIND=gateway
Environment=OPENCLAW_SERVICE_VERSION=2026.2.19-2

[Install]
WantedBy=default.target

# /home/jeebs/.config/systemd/user/openclaw-gateway.service.d/10-provider-lock.conf
[Service]
# Hard lock providers: exclude Anthropic entirely.
Environment=OPENCLAW_PROVIDER_ALLOWLIST=local_vllm,minimax-portal
Environment=ENABLE_LOCAL_VLLM=1
Environment=OPENCLAW_PREFER_LOCAL=0
Environment=OPENCLAW_DEFAULT_PROVIDER=minimax-portal

# /home/jeebs/.config/systemd/user/openclaw-gateway.service.d/override.conf
[Service]
ExecStart=
ExecStart=/usr/bin/node /home/jeebs/src/clawd/.runtime/openclaw/dist/index.js gateway --port 18789
Environment=OPENCLAW_STRICT_TOOL_PAYLOAD=1
Environment=OPENCLAW_TRACE_VLLM_OUTBOUND=1
Environment=OPENCLAW_VLLM_TOKEN_GUARD=1
Environment=OPENCLAW_VLLM_TOKEN_GUARD_MODE=reject
Environment=OPENCLAW_VLLM_CONTEXT_MAX_TOKENS=8192
-- No entries --
Feb 21 20:01:50 jeebs-Z490-AORUS-MASTER node[485223]: Node.js v22.22.0
Feb 21 20:01:50 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Main process exited, code=exited, status=1/FAILURE
Feb 21 20:01:50 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Failed with result 'exit-code'.
Feb 21 20:01:55 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Scheduled restart job, restart counter is at 113.
Feb 21 20:01:55 jeebs-Z490-AORUS-MASTER systemd[1668]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]: file:///home/jeebs/src/clawd/.runtime/openclaw/dist/reply-B4B0jUCM.js:35318
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]:         return `'${s.replace(/'/g, "'"'"'")}'`;
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]:                                    ^^^
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]: SyntaxError: missing ) after argument list
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]:     at compileSourceTextModule (node:internal/modules/esm/utils:346:16)
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]:     at ModuleLoader.moduleStrategy (node:internal/modules/esm/translators:107:18)
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]:     at #translate (node:internal/modules/esm/loader:546:20)
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]:     at afterLoad (node:internal/modules/esm/loader:596:29)
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]:     at ModuleLoader.loadAndTranslate (node:internal/modules/esm/loader:601:12)
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]:     at #createModuleJob (node:internal/modules/esm/loader:624:36)
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]:     at #getJobFromResolveResult (node:internal/modules/esm/loader:343:34)
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]:     at ModuleLoader.getModuleJobForImport (node:internal/modules/esm/loader:311:41)
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]: Node.js v22.22.0
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Main process exited, code=exited, status=1/FAILURE
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Failed with result 'exit-code'.
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Scheduled restart job, restart counter is at 114.
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER systemd[1668]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]: file:///home/jeebs/src/clawd/.runtime/openclaw/dist/reply-B4B0jUCM.js:35318
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]:         return `'${s.replace(/'/g, "'"'"'")}'`;
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]:                                    ^^^
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]: SyntaxError: missing ) after argument list
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]:     at compileSourceTextModule (node:internal/modules/esm/utils:346:16)
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]:     at ModuleLoader.moduleStrategy (node:internal/modules/esm/translators:107:18)
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]:     at #translate (node:internal/modules/esm/loader:546:20)
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]:     at afterLoad (node:internal/modules/esm/loader:596:29)
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]:     at ModuleLoader.loadAndTranslate (node:internal/modules/esm/loader:601:12)
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]:     at #createModuleJob (node:internal/modules/esm/loader:624:36)
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]:     at #getJobFromResolveResult (node:internal/modules/esm/loader:343:34)
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]:     at ModuleLoader.getModuleJobForImport (node:internal/modules/esm/loader:311:41)
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]: Node.js v22.22.0
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Main process exited, code=exited, status=1/FAILURE
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Failed with result 'exit-code'.
Feb 21 20:02:06 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Scheduled restart job, restart counter is at 115.
Feb 21 20:02:06 jeebs-Z490-AORUS-MASTER systemd[1668]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]: file:///home/jeebs/src/clawd/.runtime/openclaw/dist/reply-B4B0jUCM.js:35318
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]:         return `'${s.replace(/'/g, "'"'"'")}'`;
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]:                                    ^^^
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]: SyntaxError: missing ) after argument list
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]:     at compileSourceTextModule (node:internal/modules/esm/utils:346:16)
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]:     at ModuleLoader.moduleStrategy (node:internal/modules/esm/translators:107:18)
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]:     at #translate (node:internal/modules/esm/loader:546:20)
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]:     at afterLoad (node:internal/modules/esm/loader:596:29)
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]:     at ModuleLoader.loadAndTranslate (node:internal/modules/esm/loader:601:12)
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]:     at #createModuleJob (node:internal/modules/esm/loader:624:36)
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]:     at #getJobFromResolveResult (node:internal/modules/esm/loader:343:34)
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]:     at ModuleLoader.getModuleJobForImport (node:internal/modules/esm/loader:311:41)
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]: Node.js v22.22.0
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Main process exited, code=exited, status=1/FAILURE
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Failed with result 'exit-code'.
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Scheduled restart job, restart counter is at 116.
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER systemd[1668]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]: file:///home/jeebs/src/clawd/.runtime/openclaw/dist/reply-B4B0jUCM.js:35318
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]:         return `'${s.replace(/'/g, "'"'"'")}'`;
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]:                                    ^^^
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]: SyntaxError: missing ) after argument list
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]:     at compileSourceTextModule (node:internal/modules/esm/utils:346:16)
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]:     at ModuleLoader.moduleStrategy (node:internal/modules/esm/translators:107:18)
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]:     at #translate (node:internal/modules/esm/loader:546:20)
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]:     at afterLoad (node:internal/modules/esm/loader:596:29)
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]:     at ModuleLoader.loadAndTranslate (node:internal/modules/esm/loader:601:12)
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]:     at #createModuleJob (node:internal/modules/esm/loader:624:36)
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]:     at #getJobFromResolveResult (node:internal/modules/esm/loader:343:34)
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]:     at ModuleLoader.getModuleJobForImport (node:internal/modules/esm/loader:311:41)
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]: Node.js v22.22.0
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Main process exited, code=exited, status=1/FAILURE
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Failed with result 'exit-code'.
Feb 21 20:02:15 jeebs-Z490-AORUS-MASTER systemd[1668]: Stopped openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:02:15 jeebs-Z490-AORUS-MASTER systemd[1668]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:02:17 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:17.105Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
Feb 21 20:02:18 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:18.046Z [canvas] host mounted at http://127.0.0.1:18789/__openclaw__/canvas/ (root /home/jeebs/.openclaw/canvas)
Feb 21 20:02:18 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:18.084Z [heartbeat] started
Feb 21 20:02:18 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:18.087Z [health-monitor] started (interval: 300s, grace: 60s)
Feb 21 20:02:18 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:18.089Z [gateway] agent model: minimax-portal/MiniMax-M2.5
Feb 21 20:02:18 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:18.090Z [gateway] listening on ws://127.0.0.1:18789 (PID 485512)
Feb 21 20:02:18 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:18.090Z [gateway] listening on ws://[::1]:18789
Feb 21 20:02:18 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:18.092Z [gateway] log file: /tmp/openclaw/openclaw-2026-02-21.log
Feb 21 20:02:18 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:18.112Z [browser/service] Browser control service ready (profiles=2)
Feb 21 20:02:20 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:20.451Z [telegram] [default] starting provider (@jeebsdalibot)
Feb 21 20:02:20 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:20.456Z [telegram] autoSelectFamily=true (default-node22)
Feb 21 20:02:25 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:25.606Z [ws] webchat connected conn=4ca35bcb-dbe8-4ba6-9af2-9c04bf8a464b remote=127.0.0.1 client=openclaw-control-ui webchat vdev
Feb 21 20:02:25 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:25.627Z [ws] webchat connected conn=a797f1a7-4557-4880-b82f-805242da58bd remote=127.0.0.1 client=openclaw-control-ui webchat vdev
Feb 21 20:07:42 jeebs-Z490-AORUS-MASTER systemd[1668]: Stopping openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2)...
Feb 21 20:07:42 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:07:42.631Z [gateway] signal SIGTERM received
Feb 21 20:07:42 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:07:42.632Z [gateway] received SIGTERM; shutting down
Feb 21 20:07:42 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:07:42.645Z [gmail-watcher] gmail watcher stopped
Feb 21 20:07:42 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:07:42.902Z [ws] webchat disconnected code=1012 reason=service restart conn=a797f1a7-4557-4880-b82f-805242da58bd
Feb 21 20:07:42 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:07:42.903Z [ws] webchat disconnected code=1012 reason=service restart conn=4ca35bcb-dbe8-4ba6-9af2-9c04bf8a464b
Feb 21 20:07:42 jeebs-Z490-AORUS-MASTER systemd[1668]: Stopped openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:07:42 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Consumed 6.081s CPU time, 411.5M memory peak, 0B memory swap peak.
Feb 21 20:07:42 jeebs-Z490-AORUS-MASTER systemd[1668]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:07:44 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:44.347Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
Feb 21 20:07:45 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:45.262Z [canvas] host mounted at http://127.0.0.1:18789/__openclaw__/canvas/ (root /home/jeebs/.openclaw/canvas)
Feb 21 20:07:45 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:45.300Z [heartbeat] started
Feb 21 20:07:45 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:45.303Z [health-monitor] started (interval: 300s, grace: 60s)
Feb 21 20:07:45 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:45.305Z [gateway] agent model: minimax-portal/MiniMax-M2.5
Feb 21 20:07:45 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:45.306Z [gateway] listening on ws://127.0.0.1:18789 (PID 489125)
Feb 21 20:07:45 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:45.307Z [gateway] listening on ws://[::1]:18789
Feb 21 20:07:45 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:45.308Z [gateway] log file: /tmp/openclaw/openclaw-2026-02-21.log
Feb 21 20:07:45 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:45.328Z [browser/service] Browser control service ready (profiles=2)
Feb 21 20:07:45 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:45.789Z [ws] webchat connected conn=6445579a-5856-47b8-aee6-b3ab0fe0e1e9 remote=127.0.0.1 client=openclaw-control-ui webchat vdev
Feb 21 20:07:46 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:46.824Z [telegram] [default] starting provider (@jeebsdalibot)
Feb 21 20:07:46 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:46.827Z [telegram] autoSelectFamily=true (default-node22)
Feb 21 20:07:47 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:47.240Z [ws] webchat connected conn=56e404e4-67b2-48a6-a3b7-130c74314e17 remote=127.0.0.1 client=openclaw-control-ui webchat vdev
Feb 21 20:09:21 jeebs-Z490-AORUS-MASTER systemd[1668]: Stopping openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2)...
Feb 21 20:09:21 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:09:21.451Z [gateway] signal SIGTERM received
Feb 21 20:09:21 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:09:21.451Z [gateway] received SIGTERM; shutting down
Feb 21 20:09:21 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:09:21.466Z [gmail-watcher] gmail watcher stopped
Feb 21 20:09:21 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:09:21.715Z [ws] webchat disconnected code=1012 reason=service restart conn=56e404e4-67b2-48a6-a3b7-130c74314e17
Feb 21 20:09:21 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:09:21.716Z [ws] webchat disconnected code=1012 reason=service restart conn=6445579a-5856-47b8-aee6-b3ab0fe0e1e9
Feb 21 20:09:21 jeebs-Z490-AORUS-MASTER systemd[1668]: Stopped openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:09:21 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Consumed 4.664s CPU time, 194.7M memory peak, 0B memory swap peak.
Feb 21 20:09:21 jeebs-Z490-AORUS-MASTER systemd[1668]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:09:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:23.144Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
Feb 21 20:09:24 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:24.051Z [canvas] host mounted at http://127.0.0.1:18789/__openclaw__/canvas/ (root /home/jeebs/.openclaw/canvas)
Feb 21 20:09:24 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:24.088Z [heartbeat] started
Feb 21 20:09:24 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:24.091Z [health-monitor] started (interval: 300s, grace: 60s)
Feb 21 20:09:24 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:24.093Z [gateway] agent model: minimax-portal/MiniMax-M2.5
Feb 21 20:09:24 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:24.094Z [gateway] listening on ws://127.0.0.1:18789 (PID 490423)
Feb 21 20:09:24 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:24.095Z [gateway] listening on ws://[::1]:18789
Feb 21 20:09:24 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:24.096Z [gateway] log file: /tmp/openclaw/openclaw-2026-02-21.log
Feb 21 20:09:24 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:24.115Z [browser/service] Browser control service ready (profiles=2)
Feb 21 20:09:24 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:24.260Z [ws] webchat connected conn=7e80d68c-9d22-4309-b324-7cee4a1bdfac remote=127.0.0.1 client=openclaw-control-ui webchat vdev
Feb 21 20:09:25 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:25.573Z [telegram] [default] starting provider (@jeebsdalibot)
Feb 21 20:09:25 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:25.576Z [telegram] autoSelectFamily=true (default-node22)
Feb 21 20:09:25 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:25.984Z [ws] webchat connected conn=c09aba15-357c-47bc-a9b0-83f17759c473 remote=127.0.0.1 client=openclaw-control-ui webchat vdev
Feb 21 22:05:18 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T22:05:18.220+10:00 [tools] read failed: ENOENT: no such file or directory, access '/home/jeebs/.openclaw/workspace/docs/index.md'
Feb 21 22:06:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T12:06:23.177Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=137s queueDepth=1
Feb 21 22:12:57 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T22:12:57.513+10:00 [tools] edit failed: Could not find the exact text in /home/jeebs/.openclaw/workspace/docs/multi-tier-agents-research.md. The old text must match exactly including all whitespace and newlines.
Feb 21 22:13:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T12:13:53.180Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=127s queueDepth=1
Feb 21 22:17:56 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T22:17:56.358+10:00 [tools] edit failed: Could not find the exact text in /home/jeebs/.openclaw/workspace/docs/multi-tier-agents-research.md. The old text must match exactly including all whitespace and newlines.
Feb 21 22:18:05 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T22:18:05.584+10:00 [tools] edit failed: Could not find the exact text in /home/jeebs/.openclaw/workspace/docs/multi-tier-agents-research.md. The old text must match exactly including all whitespace and newlines.
Feb 21 22:18:21 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T22:18:21.755+10:00 [tools] edit failed: Could not find the exact text in /home/jeebs/.openclaw/workspace/docs/multi-tier-agents-research.md. The old text must match exactly including all whitespace and newlines.
Feb 21 22:23:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T12:23:53.184Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=150s queueDepth=1
Feb 21 22:24:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T12:24:23.185Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=180s queueDepth=1
Feb 21 22:24:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T12:24:53.184Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=210s queueDepth=1
Feb 21 22:25:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T12:25:23.184Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=240s queueDepth=1
Feb 21 22:25:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T12:25:53.184Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=270s queueDepth=1
Feb 21 22:26:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T12:26:23.185Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=300s queueDepth=1
Feb 21 22:26:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T12:26:53.187Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=330s queueDepth=1
Feb 21 22:59:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T12:59:53.193Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=133s queueDepth=1
Feb 21 23:00:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:00:23.194Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=163s queueDepth=1
Feb 21 23:00:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:00:53.194Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=193s queueDepth=1
Feb 21 23:01:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:01:23.195Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=223s queueDepth=1
Feb 21 23:06:01 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T23:06:01.388+10:00 [tools] read failed: ENOENT: no such file or directory, access '/home/jeebs/.openclaw/workspace/memory/2026-02-21.md'
Feb 21 23:07:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:07:23.196Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=150s queueDepth=1
Feb 21 23:07:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:07:53.196Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=180s queueDepth=1
Feb 21 23:08:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:08:23.197Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=210s queueDepth=1
Feb 21 23:08:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:08:53.197Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=240s queueDepth=1
Feb 21 23:38:10 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T23:38:10.483+10:00 typing TTL reached (2m); stopping typing indicator
Feb 21 23:38:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:38:23.206Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=131s queueDepth=1
Feb 21 23:38:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:38:53.205Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=161s queueDepth=1
Feb 21 23:39:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:39:23.205Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=191s queueDepth=1
Feb 21 23:39:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:39:53.206Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=221s queueDepth=1
Feb 21 23:40:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:40:23.206Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=251s queueDepth=1
Feb 21 23:40:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:40:53.207Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=281s queueDepth=1
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T14:53:22.344Z [ws] webchat disconnected code=1006 reason=n/a conn=7e80d68c-9d22-4309-b324-7cee4a1bdfac
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T14:53:22.346Z [ws] webchat disconnected code=1006 reason=n/a conn=c09aba15-357c-47bc-a9b0-83f17759c473
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER systemd[1668]: Stopping openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2)...
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T14:53:22.498Z [gateway] signal SIGTERM received
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T14:53:22.499Z [gateway] received SIGTERM; shutting down
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T14:53:22.514Z [gmail-watcher] gmail watcher stopped
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER systemd[1668]: Stopped openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Consumed 47.769s CPU time, 203.3M memory peak, 0B memory swap peak.
-- Boot 45b35623d291431fa703c9232d2ea952 --
Feb 22 06:34:42 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 22 06:34:44 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:34:44.429Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
Feb 22 06:34:58 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:34:58.494Z [canvas] host mounted at http://127.0.0.1:18789/__openclaw__/canvas/ (root /home/jeebs/.openclaw/canvas)
Feb 22 06:34:58 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:34:58.543Z [heartbeat] started
Feb 22 06:34:58 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:34:58.545Z [health-monitor] started (interval: 300s, grace: 60s)
Feb 22 06:34:58 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:34:58.547Z [gateway] agent model: minimax-portal/MiniMax-M2.5
Feb 22 06:34:58 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:34:58.548Z [gateway] listening on ws://127.0.0.1:18789 (PID 1682)
Feb 22 06:34:58 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:34:58.549Z [gateway] listening on ws://[::1]:18789
Feb 22 06:34:58 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:34:58.550Z [gateway] log file: /tmp/openclaw/openclaw-2026-02-22.log
Feb 22 06:34:58 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:34:58.576Z [browser/service] Browser control service ready (profiles=2)
Feb 22 06:34:58 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:34:58.873Z [gateway] update available (latest): v2026.2.21-2 (current v2026.2.19-2). Run: openclaw update
Feb 22 06:35:00 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:35:00.932Z [telegram] [default] starting provider (@jeebsdalibot)
Feb 22 06:35:00 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:35:00.935Z [telegram] autoSelectFamily=true (default-node22)
Feb 22 06:35:53 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:35:53.302Z [gateway] security audit: device access upgrade requested reason=scope-upgrade device=d59e8530ab5264cdd8fc054743aa677883e0705f191cc4d5f6c3bd5fc07bf301 ip=unknown-ip auth=token roleFrom=operator roleTo=operator scopesFrom=operator.admin,operator.approvals,operator.pairing scopesTo=operator.write client=gateway-client conn=5a8ca0b7-af47-456a-aa00-ee86228cb94f
Feb 22 06:35:53 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-22T06:35:53.305+10:00 gateway connect failed: Error: pairing required
Feb 22 06:35:53 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-22T06:35:53.308+10:00 Subagent completion direct announce failed for run b1a26796-f74b-4f78-92b0-25416e1e5ec9:78ca328f-460e-404d-8d10-2c48e2712048: gateway closed (1008): pairing required
Feb 22 06:35:53 jeebs-Z490-AORUS-MASTER node[1682]: Gateway target: ws://127.0.0.1:18789
Feb 22 06:35:53 jeebs-Z490-AORUS-MASTER node[1682]: Source: local loopback
Feb 22 06:35:53 jeebs-Z490-AORUS-MASTER node[1682]: Config: /home/jeebs/.openclaw/openclaw.json
Feb 22 06:35:53 jeebs-Z490-AORUS-MASTER node[1682]: Bind: loopback
Feb 22 06:35:53 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:35:53.316Z [ws] closed before connect conn=5a8ca0b7-af47-456a-aa00-ee86228cb94f remote=127.0.0.1 fwd=n/a origin=n/a host=127.0.0.1:18789 ua=n/a code=1008 reason=pairing required
Feb 22 06:38:15 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:38:15.886Z [telegram] telegram_handler_finally chatId=8159253715 messageId=516
Feb 22 06:39:38 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:39:38.190Z [telegram] telegram_handler_finally chatId=8159253715 messageId=518
Feb 22 06:39:38 jeebs-Z490-AORUS-MASTER node[1682]: {"event":"telegram_handler_failed","correlation_id":"tg-mlws8eku-001","update_id":518,"stage":"pipeline","err_class":"Error","err_message":"telegram handler timed out after 25000ms"}
Feb 22 06:39:38 jeebs-Z490-AORUS-MASTER node[1682]: {"event":"telegram_deadletter_write_failed","error":"TypeError: fs$1.mkdirSync is not a function"}
Feb 22 06:39:38 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:39:38.194Z [telegram] handler failed (correlation_id=tg-mlws8eku-001, stage=pipeline): telegram handler timed out after 25000ms
Feb 22 06:40:39 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:40:39.042Z [telegram] telegram_handler_finally chatId=8159253715 messageId=521
Feb 22 06:40:39 jeebs-Z490-AORUS-MASTER node[1682]: {"event":"telegram_handler_failed","correlation_id":"tg-mlws9pj6-002","update_id":521,"stage":"pipeline","err_class":"Error","err_message":"telegram handler timed out after 25000ms"}
Feb 22 06:40:39 jeebs-Z490-AORUS-MASTER node[1682]: {"event":"telegram_deadletter_write_failed","error":"TypeError: fs$1.mkdirSync is not a function"}
Feb 22 06:40:39 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:40:39.045Z [telegram] handler failed (correlation_id=tg-mlws9pj6-002, stage=pipeline): telegram handler timed out after 25000ms
Feb 22 06:40:40 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:40:40.452Z [telegram] telegram_handler_finally chatId=8159253715 messageId=522
Feb 22 06:40:51 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:40:51.796Z [telegram] telegram_handler_finally chatId=8159253715 messageId=524
-- No entries --
-- No entries --
-rw-r--r-- 1 root root 1136 Mar 31  2024 /etc/crontab

/etc/cron.d:
total 32
drwxr-xr-x   2 root root  4096 Feb 10 10:29 .
drwxr-xr-x 144 root root 12288 Feb 21 06:49 ..
-rw-r--r--   1 root root   102 Mar 31  2024 .placeholder
-rw-r--r--   1 root root   219 Nov 17  2023 anacron
-rw-r--r--   1 root root   201 Apr  9  2024 e2scrub_all
-rw-r--r--   1 root root   396 Jan 10  2024 sysstat

/etc/cron.daily:
total 48
drwxr-xr-x   2 root root  4096 Feb 18 21:52 .
drwxr-xr-x 144 root root 12288 Feb 21 06:49 ..
-rw-r--r--   1 root root   102 Mar 31  2024 .placeholder
-rwxr-xr-x   1 root root   311 Sep 26  2023 0anacron
-rwxr-xr-x   1 root root   376 Jul  9  2025 apport
-rwxr-xr-x   1 root root  1478 Mar 22  2024 apt-compat
-rwxr-xr-x   1 root root   123 Feb  5  2024 dpkg
lrwxrwxrwx   1 root root    37 Feb 13 05:44 google-chrome -> /opt/google/chrome/cron/google-chrome
-rwxr-xr-x   1 root root   377 Apr  9  2024 logrotate
-rwxr-xr-x   1 root root  1395 Mar 30  2024 man-db
-rwxr-xr-x   1 root root   518 Jan 10  2024 sysstat

/etc/cron.hourly:
total 20
drwxr-xr-x   2 root root  4096 Feb 10 10:19 .
drwxr-xr-x 144 root root 12288 Feb 21 06:49 ..
-rw-r--r--   1 root root   102 Mar 31  2024 .placeholder

/etc/cron.monthly:
total 24
drwxr-xr-x   2 root root  4096 Feb 10 10:28 .
drwxr-xr-x 144 root root 12288 Feb 21 06:49 ..
-rw-r--r--   1 root root   102 Mar 31  2024 .placeholder
-rwxr-xr-x   1 root root   313 Sep 26  2023 0anacron

/etc/cron.weekly:
total 28
drwxr-xr-x   2 root root  4096 Feb 10 10:29 .
drwxr-xr-x 144 root root 12288 Feb 21 06:49 ..
-rw-r--r--   1 root root   102 Mar 31  2024 .placeholder
-rwxr-xr-x   1 root root   312 Sep 26  2023 0anacron
-rwxr-xr-x   1 root root  1055 Mar 30  2024 man-db

/etc/cron.yearly:
total 20
drwxr-xr-x   2 root root  4096 Feb 10 10:19 .
drwxr-xr-x 144 root root 12288 Feb 21 06:49 ..
-rw-r--r--   1 root root   102 Mar 31  2024 .placeholder
# OpenClaw maintenance
30 2 * * * $HOME/bin/openclaw-backup.sh >> $HOME/.local/state/openclaw/backup.log 2>&1
45 3 * * * $HOME/bin/python-env-audit.sh $HOME/security-audits >> $HOME/.local/state/openclaw/python-audit.log 2>&1
15 4 * * * $HOME/bin/cleanup-temp.sh >> $HOME/.local/state/openclaw/cleanup.log 2>&1
*/5 * * * * $HOME/bin/system-monitor.sh >> $HOME/.local/state/openclaw/monitor-cron.log 2>&1
NEXT                           LEFT LAST                               PASSED UNIT                           ACTIVATES
Sun 2026-02-22 07:00:00 AEST   8min Sun 2026-02-22 06:50:01 AEST 1min 35s ago sysstat-collect.timer          sysstat-collect.service
Sun 2026-02-22 07:18:04 AEST  26min Sun 2026-02-22 00:36:03 AEST            - fwupd-refresh.timer            fwupd-refresh.service
Sun 2026-02-22 07:26:25 AEST  34min Sat 2026-02-21 06:48:58 AEST            - apt-daily-upgrade.timer        apt-daily-upgrade.service
Sun 2026-02-22 07:33:03 AEST  41min Sat 2026-02-21 23:31:29 AEST            - anacron.timer                  anacron.service
Sun 2026-02-22 13:29:16 AEST     6h Sat 2026-02-21 20:11:28 AEST            - motd-news.timer                motd-news.service
Sun 2026-02-22 14:34:52 AEST     7h Sat 2026-02-21 19:18:31 AEST            - apt-daily.timer                apt-daily.service
Mon 2026-02-23 00:00:00 AEST    17h Sun 2026-02-22 00:00:01 AEST            - dpkg-db-backup.timer           dpkg-db-backup.service
Mon 2026-02-23 00:00:00 AEST    17h Sun 2026-02-22 00:00:01 AEST            - logrotate.timer                logrotate.service
Mon 2026-02-23 00:07:00 AEST    17h -                                       - sysstat-summary.timer          sysstat-summary.service
Mon 2026-02-23 00:30:22 AEST    17h Tue 2026-02-17 14:08:18 AEST            - fstrim.timer                   fstrim.service
Mon 2026-02-23 01:04:43 AEST    18h Sun 2026-02-22 06:46:46 AEST 4min 50s ago man-db.timer                   man-db.service
Mon 2026-02-23 06:39:40 AEST    23h Sun 2026-02-22 06:39:40 AEST    11min ago update-notifier-download.timer update-notifier-download.service
Mon 2026-02-23 06:49:34 AEST    23h Sun 2026-02-22 06:49:34 AEST  2min 1s ago systemd-tmpfiles-clean.timer   systemd-tmpfiles-clean.service
Thu 2026-02-26 15:41:06 AEST 4 days Tue 2026-02-17 14:08:30 AEST            - update-notifier-motd.timer     update-notifier-motd.service
Sun 2026-03-01 03:10:32 AEST 6 days Sun 2026-02-22 06:35:16 AEST    16min ago e2scrub_all.timer              e2scrub_all.service
-                                 - -                                       - apport-autoreport.timer        apport-autoreport.service
-                                 - -                                       - snapd.snap-repair.timer        snapd.snap-repair.service
-                                 - -                                       - ua-timer.timer                 ua-timer.service

18 timers listed.
NEXT                            LEFT LAST                            PASSED UNIT                                          ACTIVATES
Sun 2026-02-22 09:00:00 AEST 2h 8min -                                    - snap.firmware-updater.firmware-notifier.timer snap.firmware-updater.firmware-notifier.service
Mon 2026-02-23 06:39:48 AEST     23h Sun 2026-02-22 06:39:48 AEST 11min ago launchpadlib-cache-clean.timer                launchpadlib-cache-clean.service

2 timers listed.
```

## Phase 3 Script Inspection

```bash
ls -la ~/bin/python-env-audit.sh || true
sed -n '1,200p' ~/bin/python-env-audit.sh || true
sed -n '200,400p' ~/bin/python-env-audit.sh || true
grep -nE 'vllm|api_server|8001|openclaw|systemctl|nohup|daemon|start|restart|pkill|kill' ~/bin/python-env-audit.sh || true

ls -la ~/.local/state/openclaw/ || true
ls -la ~/.local/state/openclaw/python-audit.log || true
tail -n 200 ~/.local/state/openclaw/python-audit.log 2>/dev/null || true
```

```text
-rwxr-xr-x 1 jeebs jeebs 661 Feb 18 21:38 /home/jeebs/bin/python-env-audit.sh
#!/usr/bin/env bash
set -euo pipefail
OUT_DIR="${1:-${HOME}/security-audits}"
mkdir -p "${OUT_DIR}"
TS="$(date +%Y%m%dT%H%M%S)"
OUT="${OUT_DIR}/python-audit-${TS}.txt"
{
  echo "== Python environment audit =="
  date -Is
  for py in python3 "$HOME/src/clawd/.venv/bin/python" "$HOME/src/clawd/.venv-vllm/bin/python"; do
    [ -x "$py" ] || continue
    echo
    echo "--- $py ---"
    "$py" -V || true
    "$py" -m pip check || true
    "$py" -m pip list --outdated || true
    if "$py" -m pip show pip-audit >/dev/null 2>&1; then
      "$py" -m pip_audit || true
    else
      echo "pip-audit not installed for $py"
    fi
  done
} > "$OUT"
echo "Wrote $OUT"
10:  for py in python3 "$HOME/src/clawd/.venv/bin/python" "$HOME/src/clawd/.venv-vllm/bin/python"; do
total 112
drwxrwxr-x 2 jeebs jeebs  4096 Feb 18 21:40 .
drwx------ 4 jeebs jeebs  4096 Feb 18 21:38 ..
-rw-rw-r-- 1 jeebs jeebs 49056 Feb 22 06:50 monitor-cron.log
-rw-rw-r-- 1 jeebs jeebs 49056 Feb 22 06:50 monitor.log
ls: cannot access '/home/jeebs/.local/state/openclaw/python-audit.log': No such file or directory
```

## Phase 2b Focused vLLM Launcher Attribution

```bash
# Focused vLLM launcher attribution
systemctl status vllm-assistant.service --no-pager || true
systemctl cat vllm-assistant.service 2>/dev/null || true
journalctl -u vllm-assistant.service -n 200 --no-pager || true

systemctl --user status openclaw-vllm.service --no-pager || true
systemctl --user cat openclaw-vllm.service 2>/dev/null || true
journalctl --user -u openclaw-vllm.service -n 200 --no-pager || true

# Check enablement state for both units
systemctl is-enabled vllm-assistant.service || true
systemctl --user is-enabled openclaw-vllm.service || true

# show explicit PIDs for current listeners and related services
ss -ltnp | grep -E '(:8001)\b' || true
pgrep -af 'vllm serve|openai.api_server|local-assistant' || true
```

```text
● vllm-assistant.service - vLLM OpenAI Server (assistant)
     Loaded: loaded (/etc/systemd/system/vllm-assistant.service; enabled; preset: enabled)
     Active: active (running) since Sun 2026-02-22 06:35:31 AEST; 17min ago
   Main PID: 3285 (vllm)
      Tasks: 161 (limit: 38169)
     Memory: 2.2G (peak: 2.2G)
        CPU: 44.764s
     CGroup: /system.slice/vllm-assistant.service
             ├─3285 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8
             ├─3360 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c "from multiprocessing.resource_tracker import main;main(34)"
             └─3361 VLLM::EngineCore

Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/embeddings, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /score, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/score, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /rerank, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/rerank, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v2/rerank, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /pooling, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO:     Started server process [3285]
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO:     Waiting for application startup.
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO:     Application startup complete.
# /etc/systemd/system/vllm-assistant.service
[Unit]
Description=vLLM OpenAI Server (assistant)
After=network.target
Wants=network.target

[Service]
Type=simple
User=jeebs
WorkingDirectory=/opt/models
Environment=HF_HOME=/opt/models/.hf
Environment=TRANSFORMERS_CACHE=/opt/models/.hf
ExecStart=/usr/bin/env bash -lc '\
  source /home/jeebs/src/clawd/.venv-vllm/bin/activate && \
  vllm serve /opt/models/qwen2_5_14b_instruct_awq \
    --served-model-name local-assistant \
    --host 127.0.0.1 --port 8001 \
    --quantization awq \
    --dtype auto \
    --gpu-memory-utilization 0.90 \
    --max-model-len 16384 \
    --max-num-seqs 8'
Restart=on-failure
RestartSec=2
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
Feb 22 06:35:18 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) INFO 02-22 06:35:18 [backends.py:872] Dynamo bytecode transform time: 7.37 s
Feb 22 06:35:26 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) INFO 02-22 06:35:26 [backends.py:267] Directly load the compiled graph(s) for compile range (1, 2048) from the cache, took 1.908 s
Feb 22 06:35:26 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) INFO 02-22 06:35:26 [monitor.py:34] torch.compile takes 9.27 s in total
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) INFO 02-22 06:35:27 [gpu_worker.py:356] Available KV cache memory: 1.87 GiB
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946] EngineCore failed to start.
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946] Traceback (most recent call last):
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 937, in run_engine_core
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]     engine_core = EngineCoreProc(*args, engine_index=dp_rank, **kwargs)
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 691, in __init__
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]     super().__init__(
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 112, in __init__
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]     num_gpu_blocks, num_cpu_blocks, kv_cache_config = self._initialize_kv_caches(
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]                                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 253, in _initialize_kv_caches
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]     kv_cache_configs = get_kv_cache_configs(
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]                        ^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/core/kv_cache_utils.py", line 1516, in get_kv_cache_configs
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]     _check_enough_kv_cache_memory(
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/core/kv_cache_utils.py", line 634, in _check_enough_kv_cache_memory
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]     raise ValueError(
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946] ValueError: To serve at least one request with the models's max seq len (16384), (3.0 GiB KV cache is needed, which is larger than the available KV cache memory (1.87 GiB). Based on the available memory, the estimated maximum model length is 10224. Try increasing `gpu_memory_utilization` or decreasing `max_model_len` when initializing the engine. See https://docs.vllm.ai/en/latest/configuration/conserving_memory/ for more details.
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) Process EngineCore_DP0:
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) Traceback (most recent call last):
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)   File "/usr/lib/python3.12/multiprocessing/process.py", line 314, in _bootstrap
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)     self.run()
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)   File "/usr/lib/python3.12/multiprocessing/process.py", line 108, in run
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)     self._target(*self._args, **self._kwargs)
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 950, in run_engine_core
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)     raise e
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 937, in run_engine_core
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)     engine_core = EngineCoreProc(*args, engine_index=dp_rank, **kwargs)
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 691, in __init__
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)     super().__init__(
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 112, in __init__
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)     num_gpu_blocks, num_cpu_blocks, kv_cache_config = self._initialize_kv_caches(
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)                                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 253, in _initialize_kv_caches
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)     kv_cache_configs = get_kv_cache_configs(
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)                        ^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/core/kv_cache_utils.py", line 1516, in get_kv_cache_configs
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)     _check_enough_kv_cache_memory(
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/core/kv_cache_utils.py", line 634, in _check_enough_kv_cache_memory
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)     raise ValueError(
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ValueError: To serve at least one request with the models's max seq len (16384), (3.0 GiB KV cache is needed, which is larger than the available KV cache memory (1.87 GiB). Based on the available memory, the estimated maximum model length is 10224. Try increasing `gpu_memory_utilization` or decreasing `max_model_len` when initializing the engine. See https://docs.vllm.ai/en/latest/configuration/conserving_memory/ for more details.
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: [rank0]:[W222 06:35:27.321548260 ProcessGroupNCCL.cpp:1524] Warning: WARNING: destroy_process_group() was not called before program exit, which can leak resources. For more info, please see https://pytorch.org/docs/stable/distributed.html#shutdown (function operator())
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633) Traceback (most recent call last):
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/bin/vllm", line 6, in <module>
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     sys.exit(main())
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)              ^^^^^^
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/cli/main.py", line 73, in main
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     args.dispatch_function(args)
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/cli/serve.py", line 111, in cmd
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     uvloop.run(run_server(args))
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/uvloop/__init__.py", line 96, in run
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     return __asyncio.run(
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)            ^^^^^^^^^^^^^^
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/usr/lib/python3.12/asyncio/runners.py", line 194, in run
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     return runner.run(main)
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)            ^^^^^^^^^^^^^^^^
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/usr/lib/python3.12/asyncio/runners.py", line 118, in run
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     return self._loop.run_until_complete(task)
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/uvloop/__init__.py", line 48, in wrapper
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     return await main
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)            ^^^^^^^^^^
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 919, in run_server
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     await run_server_worker(listen_address, sock, args, **uvicorn_kwargs)
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 938, in run_server_worker
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     async with build_async_engine_client(
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/usr/lib/python3.12/contextlib.py", line 210, in __aenter__
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     return await anext(self.gen)
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)            ^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 147, in build_async_engine_client
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     async with build_async_engine_client_from_engine_args(
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/usr/lib/python3.12/contextlib.py", line 210, in __aenter__
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     return await anext(self.gen)
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)            ^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 188, in build_async_engine_client_from_engine_args
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     async_llm = AsyncLLM.from_vllm_config(
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)                 ^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/async_llm.py", line 228, in from_vllm_config
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     return cls(
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)            ^^^^
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/async_llm.py", line 155, in __init__
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     self.engine_core = EngineCoreClient.make_async_mp_client(
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core_client.py", line 122, in make_async_mp_client
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     return AsyncMPClient(*client_args)
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)            ^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core_client.py", line 819, in __init__
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     super().__init__(
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core_client.py", line 479, in __init__
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     with launch_core_engines(vllm_config, executor_class, log_stats) as (
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/usr/lib/python3.12/contextlib.py", line 144, in __exit__
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     next(self.gen)
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/utils.py", line 933, in launch_core_engines
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     wait_for_engine_startup(
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/utils.py", line 992, in wait_for_engine_startup
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     raise RuntimeError(
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633) RuntimeError: Engine core initialization failed. See root cause above. Failed core proc(s): {}
Feb 22 06:35:29 jeebs-Z490-AORUS-MASTER systemd[1]: vllm-assistant.service: Main process exited, code=exited, status=1/FAILURE
Feb 22 06:35:29 jeebs-Z490-AORUS-MASTER systemd[1]: vllm-assistant.service: Failed with result 'exit-code'.
Feb 22 06:35:29 jeebs-Z490-AORUS-MASTER systemd[1]: vllm-assistant.service: Consumed 38.244s CPU time.
Feb 22 06:35:31 jeebs-Z490-AORUS-MASTER systemd[1]: vllm-assistant.service: Scheduled restart job, restart counter is at 1.
Feb 22 06:35:31 jeebs-Z490-AORUS-MASTER systemd[1]: Started vllm-assistant.service - vLLM OpenAI Server (assistant).
Feb 22 06:35:32 jeebs-Z490-AORUS-MASTER env[3285]: /home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/transformers/utils/hub.py:110: FutureWarning: Using `TRANSFORMERS_CACHE` is deprecated and will be removed in v5 of Transformers. Use `HF_HOME` instead.
Feb 22 06:35:32 jeebs-Z490-AORUS-MASTER env[3285]:   warnings.warn(
Feb 22 06:35:35 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:35 [utils.py:325]
Feb 22 06:35:35 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:35 [utils.py:325]        █     █     █▄   ▄█
Feb 22 06:35:35 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:35 [utils.py:325]  ▄▄ ▄█ █     █     █ ▀▄▀ █  version 0.15.1
Feb 22 06:35:35 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:35 [utils.py:325]   █▄█▀ █     █     █     █  model   /opt/models/qwen2_5_14b_instruct_awq
Feb 22 06:35:35 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:35 [utils.py:325]    ▀▀  ▀▀▀▀▀ ▀▀▀▀▀ ▀     ▀
Feb 22 06:35:35 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:35 [utils.py:325]
Feb 22 06:35:35 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:35 [utils.py:261] non-default args: {'model_tag': '/opt/models/qwen2_5_14b_instruct_awq', 'api_server_count': 1, 'host': '127.0.0.1', 'port': 8001, 'model': '/opt/models/qwen2_5_14b_instruct_awq', 'max_model_len': 16384, 'quantization': 'awq', 'served_model_name': ['local-assistant'], 'max_num_seqs': 8}
Feb 22 06:35:35 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:35 [model.py:541] Resolved architecture: Qwen2ForCausalLM
Feb 22 06:35:35 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:35 [model.py:1561] Using max model len 16384
Feb 22 06:35:35 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:35 [awq_marlin.py:166] Detected that the model can run with awq_marlin, however you specified quantization=awq explicitly, so forcing awq. Use quantization=awq_marlin for faster inference
Feb 22 06:35:36 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:36 [scheduler.py:226] Chunked prefill is enabled with max_num_batched_tokens=2048.
Feb 22 06:35:36 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:36 [vllm.py:624] Asynchronous scheduling is enabled.
Feb 22 06:35:38 jeebs-Z490-AORUS-MASTER env[3361]: /home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/transformers/utils/hub.py:110: FutureWarning: Using `TRANSFORMERS_CACHE` is deprecated and will be removed in v5 of Transformers. Use `HF_HOME` instead.
Feb 22 06:35:38 jeebs-Z490-AORUS-MASTER env[3361]:   warnings.warn(
Feb 22 06:35:40 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:40 [core.py:96] Initializing a V1 LLM engine (v0.15.1) with config: model='/opt/models/qwen2_5_14b_instruct_awq', speculative_config=None, tokenizer='/opt/models/qwen2_5_14b_instruct_awq', skip_tokenizer_init=False, tokenizer_mode=auto, revision=None, tokenizer_revision=None, trust_remote_code=False, dtype=torch.float16, max_seq_len=16384, download_dir=None, load_format=auto, tensor_parallel_size=1, pipeline_parallel_size=1, data_parallel_size=1, disable_custom_all_reduce=False, quantization=awq, enforce_eager=False, enable_return_routed_experts=False, kv_cache_dtype=auto, device_config=cuda, structured_outputs_config=StructuredOutputsConfig(backend='auto', disable_fallback=False, disable_any_whitespace=False, disable_additional_properties=False, reasoning_parser='', reasoning_parser_plugin='', enable_in_reasoning=False), observability_config=ObservabilityConfig(show_hidden_metrics_for_version=None, otlp_traces_endpoint=None, collect_detailed_traces=None, kv_cache_metrics=False, kv_cache_metrics_sample=0.01, cudagraph_metrics=False, enable_layerwise_nvtx_tracing=False, enable_mfu_metrics=False, enable_mm_processor_stats=False, enable_logging_iteration_details=False), seed=0, served_model_name=local-assistant, enable_prefix_caching=True, enable_chunked_prefill=True, pooler_config=None, compilation_config={'level': None, 'mode': <CompilationMode.VLLM_COMPILE: 3>, 'debug_dump_path': None, 'cache_dir': '', 'compile_cache_save_format': 'binary', 'backend': 'inductor', 'custom_ops': ['none'], 'splitting_ops': ['vllm::unified_attention', 'vllm::unified_attention_with_output', 'vllm::unified_mla_attention', 'vllm::unified_mla_attention_with_output', 'vllm::mamba_mixer2', 'vllm::mamba_mixer', 'vllm::short_conv', 'vllm::linear_attention', 'vllm::plamo2_mamba_mixer', 'vllm::gdn_attention_core', 'vllm::kda_attention', 'vllm::sparse_attn_indexer', 'vllm::rocm_aiter_sparse_attn_indexer', 'vllm::unified_kv_cache_update'], 'compile_mm_encoder': False, 'compile_sizes': [], 'compile_ranges_split_points': [2048], 'inductor_compile_config': {'enable_auto_functionalized_v2': False, 'combo_kernels': True, 'benchmark_combo_kernel': True}, 'inductor_passes': {}, 'cudagraph_mode': <CUDAGraphMode.FULL_AND_PIECEWISE: (2, 1)>, 'cudagraph_num_of_warmups': 1, 'cudagraph_capture_sizes': [1, 2, 4, 8, 16], 'cudagraph_copy_inputs': False, 'cudagraph_specialize_lora': True, 'use_inductor_graph_partition': False, 'pass_config': {'fuse_norm_quant': False, 'fuse_act_quant': False, 'fuse_attn_quant': False, 'eliminate_noops': True, 'enable_sp': False, 'fuse_gemm_comms': False, 'fuse_allreduce_rms': False}, 'max_cudagraph_capture_size': 16, 'dynamic_shapes_config': {'type': <DynamicShapesType.BACKED: 'backed'>, 'evaluate_guards': False, 'assume_32_bit_indexing': True}, 'local_cache_dir': None, 'static_all_moe_layers': []}
Feb 22 06:35:40 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:40 [parallel_state.py:1212] world_size=1 rank=0 local_rank=0 distributed_init_method=tcp://192.168.0.162:49255 backend=nccl
Feb 22 06:35:41 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:41 [parallel_state.py:1423] rank 0 in world size 1 is assigned as DP rank 0, PP rank 0, PCP rank 0, TP rank 0, EP rank N/A
Feb 22 06:35:41 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:41 [gpu_model_runner.py:4033] Starting to load model /opt/models/qwen2_5_14b_instruct_awq...
Feb 22 06:35:42 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) /home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/tvm_ffi/_optional_torch_c_dlpack.py:174: UserWarning: Failed to JIT torch c dlpack extension, EnvTensorAllocator will not be enabled.
Feb 22 06:35:42 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) We recommend installing via `pip install torch-c-dlpack-ext`
Feb 22 06:35:42 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361)   warnings.warn(
Feb 22 06:35:42 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:42 [cuda.py:364] Using FLASH_ATTN attention backend out of potential backends: ('FLASH_ATTN', 'FLASHINFER', 'TRITON_ATTN', 'FLEX_ATTENTION')
Feb 22 06:35:43 jeebs-Z490-AORUS-MASTER env[3361]: [103B blob data]
Feb 22 06:35:43 jeebs-Z490-AORUS-MASTER env[3361]: [111B blob data]
Feb 22 06:35:44 jeebs-Z490-AORUS-MASTER env[3361]: [111B blob data]
Feb 22 06:35:44 jeebs-Z490-AORUS-MASTER env[3361]: [111B blob data]
Feb 22 06:35:44 jeebs-Z490-AORUS-MASTER env[3361]: [111B blob data]
Feb 22 06:35:44 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361)
Feb 22 06:35:44 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:44 [default_loader.py:291] Loading weights took 1.74 seconds
Feb 22 06:35:45 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:45 [gpu_model_runner.py:4130] Model loading took 9.38 GiB memory and 3.424887 seconds
Feb 22 06:35:52 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:52 [backends.py:812] Using cache directory: /home/jeebs/.cache/vllm/torch_compile_cache/2e488e759d/rank_0_0/backbone for vLLM's torch.compile
Feb 22 06:35:52 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:52 [backends.py:872] Dynamo bytecode transform time: 7.05 s
Feb 22 06:35:59 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:59 [backends.py:267] Directly load the compiled graph(s) for compile range (1, 2048) from the cache, took 1.047 s
Feb 22 06:35:59 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:59 [monitor.py:34] torch.compile takes 8.10 s in total
Feb 22 06:35:59 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:59 [gpu_worker.py:356] Available KV cache memory: 11.33 GiB
Feb 22 06:35:59 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:59 [kv_cache_utils.py:1307] GPU KV cache size: 61,872 tokens
Feb 22 06:35:59 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:59 [kv_cache_utils.py:1312] Maximum concurrency for 16,384 tokens per request: 3.78x
Feb 22 06:36:00 jeebs-Z490-AORUS-MASTER env[3361]: [819B blob data]
Feb 22 06:36:01 jeebs-Z490-AORUS-MASTER env[3361]: [594B blob data]
Feb 22 06:36:01 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:36:01 [gpu_model_runner.py:5063] Graph capturing finished in 2 secs, took 0.43 GiB
Feb 22 06:36:01 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:36:01 [core.py:272] init engine (profile, create kv cache, warmup model) took 16.62 seconds
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:36:02 [vllm.py:624] Asynchronous scheduling is enabled.
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [api_server.py:665] Supported tasks: ['generate']
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) WARNING 02-22 06:36:02 [model.py:1371] Default vLLM sampling parameters have been overridden by the model's `generation_config.json`: `{'repetition_penalty': 1.05, 'temperature': 0.7, 'top_k': 20, 'top_p': 0.8}`. If this is not intended, please relaunch vLLM instance with `--generation-config vllm`.
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [serving.py:177] Warming up chat template processing...
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [hf.py:310] Detected the chat template content format to be 'string'. You can set `--chat-template-content-format` to override this.
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [serving.py:212] Chat template warmup completed in 178.6ms
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [api_server.py:946] Starting vLLM API server 0 on http://127.0.0.1:8001
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:38] Available routes are:
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /openapi.json, Methods: HEAD, GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /docs, Methods: HEAD, GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /docs/oauth2-redirect, Methods: HEAD, GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /redoc, Methods: HEAD, GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /scale_elastic_ep, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /is_scaling_elastic_ep, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /tokenize, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /detokenize, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /inference/v1/generate, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /pause, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /resume, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /is_paused, Methods: GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /metrics, Methods: GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /health, Methods: GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/chat/completions, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/chat/completions/render, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/responses, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/responses/{response_id}, Methods: GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/responses/{response_id}/cancel, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/audio/transcriptions, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/audio/translations, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/completions, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/completions/render, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/messages, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/models, Methods: GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /load, Methods: GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /version, Methods: GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /ping, Methods: GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /ping, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /invocations, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /classify, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/embeddings, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /score, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/score, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /rerank, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/rerank, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v2/rerank, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /pooling, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO:     Started server process [3285]
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO:     Waiting for application startup.
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO:     Application startup complete.
● openclaw-vllm.service - OpenClaw local vLLM server
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm.service; enabled; preset: enabled)
     Active: active (running) since Sun 2026-02-22 06:52:54 AEST; 3s ago
   Main PID: 14750 (python3.12)
      Tasks: 21 (limit: 38169)
     Memory: 456.7M (peak: 456.8M)
        CPU: 4.923s
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/openclaw-vllm.service
             └─14750 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8 --enable-auto-tool-choice --tool-call-parser hermes

Feb 22 06:52:49 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Consumed 16.502s CPU time.
Feb 22 06:52:54 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Scheduled restart job, restart counter is at 65.
Feb 22 06:52:54 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-vllm.service - OpenClaw local vLLM server.
# /home/jeebs/.config/systemd/user/openclaw-vllm.service
[Unit]
Description=OpenClaw local vLLM server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/jeebs/src/clawd
ExecStart=/home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8 --enable-auto-tool-choice --tool-call-parser hermes
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14520]: (EngineCore_DP0 pid=14520)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/worker/worker_base.py", line 326, in init_device
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14520]: (EngineCore_DP0 pid=14520)     self.worker.init_device()  # type: ignore
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14520]: (EngineCore_DP0 pid=14520)     ^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14520]: (EngineCore_DP0 pid=14520)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/worker/gpu_worker.py", line 235, in init_device
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14520]: (EngineCore_DP0 pid=14520)     self.requested_memory = request_memory(init_snapshot, self.cache_config)
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14520]: (EngineCore_DP0 pid=14520)                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14520]: (EngineCore_DP0 pid=14520)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/worker/utils.py", line 260, in request_memory
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14520]: (EngineCore_DP0 pid=14520)     raise ValueError(
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14520]: (EngineCore_DP0 pid=14520) ValueError: Free memory on device cuda:0 (0.85/23.56 GiB) on startup is less than desired GPU memory utilization (0.9, 21.2 GiB). Decrease GPU memory utilization or reduce GPU memory used by other processes.
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14520]: [rank0]:[W222 06:52:31.485733065 ProcessGroupNCCL.cpp:1524] Warning: WARNING: destroy_process_group() was not called before program exit, which can leak resources. For more info, please see https://pytorch.org/docs/stable/distributed.html#shutdown (function operator())
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452) Traceback (most recent call last):
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)   File "/home/jeebs/src/clawd/.venv-vllm/bin/vllm", line 6, in <module>
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)     sys.exit(main())
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)              ^^^^^^
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/cli/main.py", line 73, in main
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)     args.dispatch_function(args)
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/cli/serve.py", line 111, in cmd
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)     uvloop.run(run_server(args))
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/uvloop/__init__.py", line 96, in run
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)     return __asyncio.run(
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)            ^^^^^^^^^^^^^^
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)   File "/usr/lib/python3.12/asyncio/runners.py", line 194, in run
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)     return runner.run(main)
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)            ^^^^^^^^^^^^^^^^
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)   File "/usr/lib/python3.12/asyncio/runners.py", line 118, in run
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)     return self._loop.run_until_complete(task)
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/uvloop/__init__.py", line 48, in wrapper
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)     return await main
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)            ^^^^^^^^^^
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 919, in run_server
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)     await run_server_worker(listen_address, sock, args, **uvicorn_kwargs)
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 938, in run_server_worker
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)     async with build_async_engine_client(
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)   File "/usr/lib/python3.12/contextlib.py", line 210, in __aenter__
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)     return await anext(self.gen)
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)            ^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 147, in build_async_engine_client
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)     async with build_async_engine_client_from_engine_args(
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)   File "/usr/lib/python3.12/contextlib.py", line 210, in __aenter__
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)     return await anext(self.gen)
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)            ^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 188, in build_async_engine_client_from_engine_args
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)     async_llm = AsyncLLM.from_vllm_config(
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)                 ^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/async_llm.py", line 228, in from_vllm_config
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)     return cls(
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)            ^^^^
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/async_llm.py", line 155, in __init__
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)     self.engine_core = EngineCoreClient.make_async_mp_client(
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core_client.py", line 122, in make_async_mp_client
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)     return AsyncMPClient(*client_args)
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)            ^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core_client.py", line 819, in __init__
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)     super().__init__(
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core_client.py", line 479, in __init__
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)     with launch_core_engines(vllm_config, executor_class, log_stats) as (
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)   File "/usr/lib/python3.12/contextlib.py", line 144, in __exit__
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)     next(self.gen)
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/utils.py", line 933, in launch_core_engines
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)     wait_for_engine_startup(
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/utils.py", line 992, in wait_for_engine_startup
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452)     raise RuntimeError(
Feb 22 06:52:31 jeebs-Z490-AORUS-MASTER python3.12[14452]: (APIServer pid=14452) RuntimeError: Engine core initialization failed. See root cause above. Failed core proc(s): {}
Feb 22 06:52:32 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Main process exited, code=exited, status=1/FAILURE
Feb 22 06:52:32 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Failed with result 'exit-code'.
Feb 22 06:52:32 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Consumed 16.534s CPU time.
Feb 22 06:52:37 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Scheduled restart job, restart counter is at 64.
Feb 22 06:52:37 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-vllm.service - OpenClaw local vLLM server.
Feb 22 06:52:42 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610) INFO 02-22 06:52:42 [utils.py:325]
Feb 22 06:52:42 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610) INFO 02-22 06:52:42 [utils.py:325]        █     █     █▄   ▄█
Feb 22 06:52:42 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610) INFO 02-22 06:52:42 [utils.py:325]  ▄▄ ▄█ █     █     █ ▀▄▀ █  version 0.15.1
Feb 22 06:52:42 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610) INFO 02-22 06:52:42 [utils.py:325]   █▄█▀ █     █     █     █  model   /opt/models/qwen2_5_14b_instruct_awq
Feb 22 06:52:42 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610) INFO 02-22 06:52:42 [utils.py:325]    ▀▀  ▀▀▀▀▀ ▀▀▀▀▀ ▀     ▀
Feb 22 06:52:42 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610) INFO 02-22 06:52:42 [utils.py:325]
Feb 22 06:52:42 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610) INFO 02-22 06:52:42 [utils.py:261] non-default args: {'model_tag': '/opt/models/qwen2_5_14b_instruct_awq', 'api_server_count': 1, 'host': '127.0.0.1', 'port': 8001, 'enable_auto_tool_choice': True, 'tool_call_parser': 'hermes', 'model': '/opt/models/qwen2_5_14b_instruct_awq', 'max_model_len': 16384, 'quantization': 'awq', 'served_model_name': ['local-assistant'], 'max_num_seqs': 8}
Feb 22 06:52:42 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610) INFO 02-22 06:52:42 [model.py:541] Resolved architecture: Qwen2ForCausalLM
Feb 22 06:52:42 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610) INFO 02-22 06:52:42 [model.py:1561] Using max model len 16384
Feb 22 06:52:42 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610) INFO 02-22 06:52:42 [awq_marlin.py:166] Detected that the model can run with awq_marlin, however you specified quantization=awq explicitly, so forcing awq. Use quantization=awq_marlin for faster inference
Feb 22 06:52:42 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610) INFO 02-22 06:52:42 [scheduler.py:226] Chunked prefill is enabled with max_num_batched_tokens=2048.
Feb 22 06:52:42 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610) INFO 02-22 06:52:42 [vllm.py:624] Asynchronous scheduling is enabled.
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) INFO 02-22 06:52:47 [core.py:96] Initializing a V1 LLM engine (v0.15.1) with config: model='/opt/models/qwen2_5_14b_instruct_awq', speculative_config=None, tokenizer='/opt/models/qwen2_5_14b_instruct_awq', skip_tokenizer_init=False, tokenizer_mode=auto, revision=None, tokenizer_revision=None, trust_remote_code=False, dtype=torch.float16, max_seq_len=16384, download_dir=None, load_format=auto, tensor_parallel_size=1, pipeline_parallel_size=1, data_parallel_size=1, disable_custom_all_reduce=False, quantization=awq, enforce_eager=False, enable_return_routed_experts=False, kv_cache_dtype=auto, device_config=cuda, structured_outputs_config=StructuredOutputsConfig(backend='auto', disable_fallback=False, disable_any_whitespace=False, disable_additional_properties=False, reasoning_parser='', reasoning_parser_plugin='', enable_in_reasoning=False), observability_config=ObservabilityConfig(show_hidden_metrics_for_version=None, otlp_traces_endpoint=None, collect_detailed_traces=None, kv_cache_metrics=False, kv_cache_metrics_sample=0.01, cudagraph_metrics=False, enable_layerwise_nvtx_tracing=False, enable_mfu_metrics=False, enable_mm_processor_stats=False, enable_logging_iteration_details=False), seed=0, served_model_name=local-assistant, enable_prefix_caching=True, enable_chunked_prefill=True, pooler_config=None, compilation_config={'level': None, 'mode': <CompilationMode.VLLM_COMPILE: 3>, 'debug_dump_path': None, 'cache_dir': '', 'compile_cache_save_format': 'binary', 'backend': 'inductor', 'custom_ops': ['none'], 'splitting_ops': ['vllm::unified_attention', 'vllm::unified_attention_with_output', 'vllm::unified_mla_attention', 'vllm::unified_mla_attention_with_output', 'vllm::mamba_mixer2', 'vllm::mamba_mixer', 'vllm::short_conv', 'vllm::linear_attention', 'vllm::plamo2_mamba_mixer', 'vllm::gdn_attention_core', 'vllm::kda_attention', 'vllm::sparse_attn_indexer', 'vllm::rocm_aiter_sparse_attn_indexer', 'vllm::unified_kv_cache_update'], 'compile_mm_encoder': False, 'compile_sizes': [], 'compile_ranges_split_points': [2048], 'inductor_compile_config': {'enable_auto_functionalized_v2': False, 'combo_kernels': True, 'benchmark_combo_kernel': True}, 'inductor_passes': {}, 'cudagraph_mode': <CUDAGraphMode.FULL_AND_PIECEWISE: (2, 1)>, 'cudagraph_num_of_warmups': 1, 'cudagraph_capture_sizes': [1, 2, 4, 8, 16], 'cudagraph_copy_inputs': False, 'cudagraph_specialize_lora': True, 'use_inductor_graph_partition': False, 'pass_config': {'fuse_norm_quant': False, 'fuse_act_quant': False, 'fuse_attn_quant': False, 'eliminate_noops': True, 'enable_sp': False, 'fuse_gemm_comms': False, 'fuse_allreduce_rms': False}, 'max_cudagraph_capture_size': 16, 'dynamic_shapes_config': {'type': <DynamicShapesType.BACKED: 'backed'>, 'evaluate_guards': False, 'assume_32_bit_indexing': True}, 'local_cache_dir': None, 'static_all_moe_layers': []}
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) INFO 02-22 06:52:47 [parallel_state.py:1212] world_size=1 rank=0 local_rank=0 distributed_init_method=tcp://192.168.0.162:37375 backend=nccl
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) INFO 02-22 06:52:47 [parallel_state.py:1423] rank 0 in world size 1 is assigned as DP rank 0, PP rank 0, PCP rank 0, TP rank 0, EP rank N/A
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946] EngineCore failed to start.
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946] Traceback (most recent call last):
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 937, in run_engine_core
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946]     engine_core = EngineCoreProc(*args, engine_index=dp_rank, **kwargs)
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946]                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 691, in __init__
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946]     super().__init__(
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 105, in __init__
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946]     self.model_executor = executor_class(vllm_config)
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946]                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/executor/abstract.py", line 101, in __init__
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946]     self._init_executor()
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/executor/uniproc_executor.py", line 47, in _init_executor
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946]     self.driver_worker.init_device()
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/worker/worker_base.py", line 326, in init_device
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946]     self.worker.init_device()  # type: ignore
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946]     ^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/worker/gpu_worker.py", line 235, in init_device
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946]     self.requested_memory = request_memory(init_snapshot, self.cache_config)
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946]                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/worker/utils.py", line 260, in request_memory
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946]     raise ValueError(
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ERROR 02-22 06:52:47 [core.py:946] ValueError: Free memory on device cuda:0 (0.85/23.56 GiB) on startup is less than desired GPU memory utilization (0.9, 21.2 GiB). Decrease GPU memory utilization or reduce GPU memory used by other processes.
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) Process EngineCore_DP0:
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) Traceback (most recent call last):
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)   File "/usr/lib/python3.12/multiprocessing/process.py", line 314, in _bootstrap
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)     self.run()
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)   File "/usr/lib/python3.12/multiprocessing/process.py", line 108, in run
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)     self._target(*self._args, **self._kwargs)
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 950, in run_engine_core
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)     raise e
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 937, in run_engine_core
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)     engine_core = EngineCoreProc(*args, engine_index=dp_rank, **kwargs)
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 691, in __init__
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)     super().__init__(
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 105, in __init__
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)     self.model_executor = executor_class(vllm_config)
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/executor/abstract.py", line 101, in __init__
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)     self._init_executor()
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/executor/uniproc_executor.py", line 47, in _init_executor
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)     self.driver_worker.init_device()
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/worker/worker_base.py", line 326, in init_device
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)     self.worker.init_device()  # type: ignore
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)     ^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/worker/gpu_worker.py", line 235, in init_device
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)     self.requested_memory = request_memory(init_snapshot, self.cache_config)
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/worker/utils.py", line 260, in request_memory
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663)     raise ValueError(
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: (EngineCore_DP0 pid=14663) ValueError: Free memory on device cuda:0 (0.85/23.56 GiB) on startup is less than desired GPU memory utilization (0.9, 21.2 GiB). Decrease GPU memory utilization or reduce GPU memory used by other processes.
Feb 22 06:52:47 jeebs-Z490-AORUS-MASTER python3.12[14663]: [rank0]:[W222 06:52:47.765355475 ProcessGroupNCCL.cpp:1524] Warning: WARNING: destroy_process_group() was not called before program exit, which can leak resources. For more info, please see https://pytorch.org/docs/stable/distributed.html#shutdown (function operator())
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610) Traceback (most recent call last):
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)   File "/home/jeebs/src/clawd/.venv-vllm/bin/vllm", line 6, in <module>
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)     sys.exit(main())
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)              ^^^^^^
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/cli/main.py", line 73, in main
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)     args.dispatch_function(args)
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/cli/serve.py", line 111, in cmd
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)     uvloop.run(run_server(args))
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/uvloop/__init__.py", line 96, in run
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)     return __asyncio.run(
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)            ^^^^^^^^^^^^^^
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)   File "/usr/lib/python3.12/asyncio/runners.py", line 194, in run
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)     return runner.run(main)
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)            ^^^^^^^^^^^^^^^^
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)   File "/usr/lib/python3.12/asyncio/runners.py", line 118, in run
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)     return self._loop.run_until_complete(task)
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/uvloop/__init__.py", line 48, in wrapper
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)     return await main
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)            ^^^^^^^^^^
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 919, in run_server
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)     await run_server_worker(listen_address, sock, args, **uvicorn_kwargs)
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 938, in run_server_worker
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)     async with build_async_engine_client(
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)   File "/usr/lib/python3.12/contextlib.py", line 210, in __aenter__
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)     return await anext(self.gen)
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)            ^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 147, in build_async_engine_client
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)     async with build_async_engine_client_from_engine_args(
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)   File "/usr/lib/python3.12/contextlib.py", line 210, in __aenter__
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)     return await anext(self.gen)
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)            ^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 188, in build_async_engine_client_from_engine_args
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)     async_llm = AsyncLLM.from_vllm_config(
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)                 ^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/async_llm.py", line 228, in from_vllm_config
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)     return cls(
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)            ^^^^
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/async_llm.py", line 155, in __init__
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)     self.engine_core = EngineCoreClient.make_async_mp_client(
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core_client.py", line 122, in make_async_mp_client
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)     return AsyncMPClient(*client_args)
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)            ^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core_client.py", line 819, in __init__
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)     super().__init__(
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core_client.py", line 479, in __init__
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)     with launch_core_engines(vllm_config, executor_class, log_stats) as (
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)   File "/usr/lib/python3.12/contextlib.py", line 144, in __exit__
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)     next(self.gen)
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/utils.py", line 933, in launch_core_engines
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)     wait_for_engine_startup(
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/utils.py", line 992, in wait_for_engine_startup
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610)     raise RuntimeError(
Feb 22 06:52:48 jeebs-Z490-AORUS-MASTER python3.12[14610]: (APIServer pid=14610) RuntimeError: Engine core initialization failed. See root cause above. Failed core proc(s): {}
Feb 22 06:52:49 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Main process exited, code=exited, status=1/FAILURE
Feb 22 06:52:49 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Failed with result 'exit-code'.
Feb 22 06:52:49 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Consumed 16.502s CPU time.
Feb 22 06:52:54 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Scheduled restart job, restart counter is at 65.
Feb 22 06:52:54 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-vllm.service - OpenClaw local vLLM server.
enabled
enabled
LISTEN 0      2048       127.0.0.1:8001       0.0.0.0:*    users:(("vllm",pid=3285,fd=25))           
3285 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8
14750 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8 --enable-auto-tool-choice --tool-call-parser hermes
14790 /bin/bash -c set -euo pipefail AUDIT='workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md' PHASE23='/tmp/dali_phase2b_cmd.sh' cat > "$PHASE23" <<'EOF' # Focused vLLM launcher attribution systemctl status vllm-assistant.service --no-pager || true systemctl cat vllm-assistant.service 2>/dev/null || true journalctl -u vllm-assistant.service -n 200 --no-pager || true  systemctl --user status openclaw-vllm.service --no-pager || true systemctl --user cat openclaw-vllm.service 2>/dev/null || true journalctl --user -u openclaw-vllm.service -n 200 --no-pager || true  # Check enablement state for both units systemctl is-enabled vllm-assistant.service || true systemctl --user is-enabled openclaw-vllm.service || true  # show explicit PIDs for current listeners and related services ss -ltnp | grep -E '(:8001)\b' || true pgrep -af 'vllm serve|openai.api_server|local-assistant' || true EOF  {   echo '## Phase 2b Focused vLLM Launcher Attribution'   echo   echo '```bash'   cat "$PHASE23"   echo '```'   echo   echo '```text' } >> "$AUDIT"  bash "$PHASE23" >> "$AUDIT" 2>&1 || true  {   echo '```'   echo } >> "$AUDIT"  echo done
```

## Phase 5 Fix Applied (Singleton Enforcement)

- Decision: keep system unit `vllm-assistant.service` as owner of `:8001`; disable competing user unit `openclaw-vllm.service`.
- Rationale: listener ownership is stable on system unit PID; user unit is in restart-loop with repeated failures while targeting same model/port.

```bash
systemctl status vllm-assistant.service --no-pager | sed -n "1,80p"
```

```text
● vllm-assistant.service - vLLM OpenAI Server (assistant)
     Loaded: loaded (/etc/systemd/system/vllm-assistant.service; enabled; preset: enabled)
     Active: active (running) since Sun 2026-02-22 06:35:31 AEST; 20min ago
   Main PID: 3285 (vllm)
      Tasks: 161 (limit: 38169)
     Memory: 2.2G (peak: 2.2G)
        CPU: 45.879s
     CGroup: /system.slice/vllm-assistant.service
             ├─3285 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8
             ├─3360 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c "from multiprocessing.resource_tracker import main;main(34)"
             └─3361 VLLM::EngineCore

Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/embeddings, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /score, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/score, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /rerank, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/rerank, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v2/rerank, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /pooling, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO:     Started server process [3285]
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO:     Waiting for application startup.
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO:     Application startup complete.
```

```bash
systemctl --user status openclaw-vllm.service --no-pager | sed -n "1,120p"
```

```text
● openclaw-vllm.service - OpenClaw local vLLM server
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm.service; enabled; preset: enabled)
     Active: active (running) since Sun 2026-02-22 06:55:53 AEST; 1s ago
   Main PID: 16374 (python3.12)
      Tasks: 20 (limit: 38169)
     Memory: 306.1M (peak: 306.1M)
        CPU: 2.517s
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/openclaw-vllm.service
             └─16374 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8 --enable-auto-tool-choice --tool-call-parser hermes

Feb 22 06:55:47 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Consumed 16.465s CPU time.
Feb 22 06:55:53 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Scheduled restart job, restart counter is at 76.
Feb 22 06:55:53 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-vllm.service - OpenClaw local vLLM server.
```

```bash
systemctl --user disable --now openclaw-vllm.service
```

```text
Removed "/home/jeebs/.config/systemd/user/default.target.wants/openclaw-vllm.service".
```

```bash
systemctl --user mask openclaw-vllm.service
```

```text
Failed to mask unit: File /home/jeebs/.config/systemd/user/openclaw-vllm.service already exists.
```

```bash
systemctl --user is-enabled openclaw-vllm.service || true
```

```text
disabled
```

```bash
systemctl is-enabled vllm-assistant.service || true
```

```text
enabled
```

```bash
systemctl --user reset-failed openclaw-vllm.service || true
```

```text
Failed to reset failed state of unit openclaw-vllm.service: Unit openclaw-vllm.service not loaded.
```

```bash
systemctl --user status openclaw-vllm.service --no-pager || true
```

```text
○ openclaw-vllm.service - OpenClaw local vLLM server
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm.service; disabled; preset: enabled)
     Active: inactive (dead)

Feb 22 06:55:47 jeebs-Z490-AORUS-MASTER python3.12[16233]: (APIServer pid=16233)     raise RuntimeError(
Feb 22 06:55:47 jeebs-Z490-AORUS-MASTER python3.12[16233]: (APIServer pid=16233) RuntimeError: Engine core initialization failed. See root cause above. Failed core proc(s): {}
Feb 22 06:55:47 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Main process exited, code=exited, status=1/FAILURE
Feb 22 06:55:47 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Failed with result 'exit-code'.
Feb 22 06:55:47 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Consumed 16.465s CPU time.
Feb 22 06:55:53 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Scheduled restart job, restart counter is at 76.
Feb 22 06:55:53 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-vllm.service - OpenClaw local vLLM server.
Feb 22 06:55:54 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopping openclaw-vllm.service - OpenClaw local vLLM server...
Feb 22 06:55:54 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopped openclaw-vllm.service - OpenClaw local vLLM server.
Feb 22 06:55:54 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Consumed 2.731s CPU time, 306.8M memory peak, 0B memory swap peak.
```

```bash
ss -ltnp | grep -E "(:8001)\\b" || true
```

```text
LISTEN 0      2048       127.0.0.1:8001       0.0.0.0:*    users:(("vllm",pid=3285,fd=25))           
```

```bash
pgrep -af "vllm serve|openai.api_server|local-assistant" || true
```

```text
3285 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8
16396 /bin/bash -c set -euo pipefail AUDIT='workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md' append_cmd() {   local cmd="$1"   {     echo '```bash'     printf '%s\n' "$cmd"     echo '```'     echo     echo '```text'   } >> "$AUDIT"   bash -lc "$cmd" >> "$AUDIT" 2>&1 || true   {     echo '```'     echo   } >> "$AUDIT" }  {   echo '## Phase 5 Fix Applied (Singleton Enforcement)'   echo   echo '- Decision: keep system unit `vllm-assistant.service` as owner of `:8001`; disable competing user unit `openclaw-vllm.service`.'   echo '- Rationale: listener ownership is stable on system unit PID; user unit is in restart-loop with repeated failures while targeting same model/port.'   echo } >> "$AUDIT"  append_cmd 'systemctl status vllm-assistant.service --no-pager | sed -n "1,80p"' append_cmd 'systemctl --user status openclaw-vllm.service --no-pager | sed -n "1,120p"' append_cmd 'systemctl --user disable --now openclaw-vllm.service' append_cmd 'systemctl --user mask openclaw-vllm.service' append_cmd 'systemctl --user is-enabled openclaw-vllm.service || true' append_cmd 'systemctl is-enabled vllm-assistant.service || true' append_cmd 'systemctl --user reset-failed openclaw-vllm.service || true' append_cmd 'systemctl --user status openclaw-vllm.service --no-pager || true' append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'pgrep -af "vllm serve|openai.api_server|local-assistant" || true'  # Phase 6 gateway evidence search {   echo '## Phase 6 Gateway Error Evidence'   echo } >> "$AUDIT" append_cmd 'journalctl --user -u openclaw-gateway.service --since "2026-02-21 20:30:00" --until "2026-02-21 20:50:00" --no-pager || true' append_cmd 'grep -RIn --color=never -E "tg-mlws9pj6-002|Gateway logs contain details" ~/.local/state/openclaw 2>/dev/null || true'  # Phase 7 verification per acceptance criteria {   echo '## Phase 7 Verification'   echo } >> "$AUDIT" append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'pgrep -af "vllm|openai.api_server|api_server" || true' append_cmd 'bash -lc "~/bin/python-env-audit.sh" || true' append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'systemctl --user restart openclaw-gateway.service' append_cmd 'sleep 2; systemctl --user status openclaw-gateway.service --no-pager | sed -n "1,80p"' append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'pgrep -af "vllm serve|openai.api_server|local-assistant" || true'  # extra: ensure no timer mentions openclaw-vllm append_cmd 'systemctl --user list-timers --all | grep -i -E "openclaw|vllm|llm|audit" || true'  echo done
16448 bash -lc pgrep -af "vllm serve|openai.api_server|local-assistant" || true
```

## Phase 6 Gateway Error Evidence

```bash
journalctl --user -u openclaw-gateway.service --since "2026-02-21 20:30:00" --until "2026-02-21 20:50:00" --no-pager || true
```

```text
-- No entries --
```

```bash
grep -RIn --color=never -E "tg-mlws9pj6-002|Gateway logs contain details" ~/.local/state/openclaw 2>/dev/null || true
```

```text
```

## Phase 7 Verification

```bash
ss -ltnp | grep -E "(:8001)\\b" || true
```

```text
LISTEN 0      2048       127.0.0.1:8001       0.0.0.0:*    users:(("vllm",pid=3285,fd=25))           
```

```bash
pgrep -af "vllm|openai.api_server|api_server" || true
```

```text
3285 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8
3360 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c from multiprocessing.resource_tracker import main;main(34)
16396 /bin/bash -c set -euo pipefail AUDIT='workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md' append_cmd() {   local cmd="$1"   {     echo '```bash'     printf '%s\n' "$cmd"     echo '```'     echo     echo '```text'   } >> "$AUDIT"   bash -lc "$cmd" >> "$AUDIT" 2>&1 || true   {     echo '```'     echo   } >> "$AUDIT" }  {   echo '## Phase 5 Fix Applied (Singleton Enforcement)'   echo   echo '- Decision: keep system unit `vllm-assistant.service` as owner of `:8001`; disable competing user unit `openclaw-vllm.service`.'   echo '- Rationale: listener ownership is stable on system unit PID; user unit is in restart-loop with repeated failures while targeting same model/port.'   echo } >> "$AUDIT"  append_cmd 'systemctl status vllm-assistant.service --no-pager | sed -n "1,80p"' append_cmd 'systemctl --user status openclaw-vllm.service --no-pager | sed -n "1,120p"' append_cmd 'systemctl --user disable --now openclaw-vllm.service' append_cmd 'systemctl --user mask openclaw-vllm.service' append_cmd 'systemctl --user is-enabled openclaw-vllm.service || true' append_cmd 'systemctl is-enabled vllm-assistant.service || true' append_cmd 'systemctl --user reset-failed openclaw-vllm.service || true' append_cmd 'systemctl --user status openclaw-vllm.service --no-pager || true' append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'pgrep -af "vllm serve|openai.api_server|local-assistant" || true'  # Phase 6 gateway evidence search {   echo '## Phase 6 Gateway Error Evidence'   echo } >> "$AUDIT" append_cmd 'journalctl --user -u openclaw-gateway.service --since "2026-02-21 20:30:00" --until "2026-02-21 20:50:00" --no-pager || true' append_cmd 'grep -RIn --color=never -E "tg-mlws9pj6-002|Gateway logs contain details" ~/.local/state/openclaw 2>/dev/null || true'  # Phase 7 verification per acceptance criteria {   echo '## Phase 7 Verification'   echo } >> "$AUDIT" append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'pgrep -af "vllm|openai.api_server|api_server" || true' append_cmd 'bash -lc "~/bin/python-env-audit.sh" || true' append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'systemctl --user restart openclaw-gateway.service' append_cmd 'sleep 2; systemctl --user status openclaw-gateway.service --no-pager | sed -n "1,80p"' append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'pgrep -af "vllm serve|openai.api_server|local-assistant" || true'  # extra: ensure no timer mentions openclaw-vllm append_cmd 'systemctl --user list-timers --all | grep -i -E "openclaw|vllm|llm|audit" || true'  echo done
16469 bash -lc pgrep -af "vllm|openai.api_server|api_server" || true
```

```bash
bash -lc "~/bin/python-env-audit.sh" || true
```

```text
Wrote /home/jeebs/security-audits/python-audit-20260222T065554.txt
```

```bash
ss -ltnp | grep -E "(:8001)\\b" || true
```

```text
LISTEN 0      2048       127.0.0.1:8001       0.0.0.0:*    users:(("vllm",pid=3285,fd=25))           
```

```bash
systemctl --user restart openclaw-gateway.service
```

```text
```

```bash
sleep 2; systemctl --user status openclaw-gateway.service --no-pager | sed -n "1,80p"
```

```text
● openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2)
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-gateway.service; enabled; preset: enabled)
    Drop-In: /home/jeebs/.config/systemd/user/openclaw-gateway.service.d
             └─10-provider-lock.conf, override.conf
     Active: active (running) since Sun 2026-02-22 06:56:23 AEST; 2s ago
   Main PID: 16591 (openclaw-gatewa)
      Tasks: 31 (limit: 38169)
     Memory: 330.3M (peak: 330.3M)
        CPU: 2.653s
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/openclaw-gateway.service
             └─16591 openclaw-gateway

Feb 22 06:56:23 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 22 06:56:24 jeebs-Z490-AORUS-MASTER node[16591]: 2026-02-21T20:56:24.960Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
```

```bash
ss -ltnp | grep -E "(:8001)\\b" || true
```

```text
LISTEN 0      2048       127.0.0.1:8001       0.0.0.0:*    users:(("vllm",pid=3285,fd=25))           
```

```bash
pgrep -af "vllm serve|openai.api_server|local-assistant" || true
```

```text
3285 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8
16396 /bin/bash -c set -euo pipefail AUDIT='workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md' append_cmd() {   local cmd="$1"   {     echo '```bash'     printf '%s\n' "$cmd"     echo '```'     echo     echo '```text'   } >> "$AUDIT"   bash -lc "$cmd" >> "$AUDIT" 2>&1 || true   {     echo '```'     echo   } >> "$AUDIT" }  {   echo '## Phase 5 Fix Applied (Singleton Enforcement)'   echo   echo '- Decision: keep system unit `vllm-assistant.service` as owner of `:8001`; disable competing user unit `openclaw-vllm.service`.'   echo '- Rationale: listener ownership is stable on system unit PID; user unit is in restart-loop with repeated failures while targeting same model/port.'   echo } >> "$AUDIT"  append_cmd 'systemctl status vllm-assistant.service --no-pager | sed -n "1,80p"' append_cmd 'systemctl --user status openclaw-vllm.service --no-pager | sed -n "1,120p"' append_cmd 'systemctl --user disable --now openclaw-vllm.service' append_cmd 'systemctl --user mask openclaw-vllm.service' append_cmd 'systemctl --user is-enabled openclaw-vllm.service || true' append_cmd 'systemctl is-enabled vllm-assistant.service || true' append_cmd 'systemctl --user reset-failed openclaw-vllm.service || true' append_cmd 'systemctl --user status openclaw-vllm.service --no-pager || true' append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'pgrep -af "vllm serve|openai.api_server|local-assistant" || true'  # Phase 6 gateway evidence search {   echo '## Phase 6 Gateway Error Evidence'   echo } >> "$AUDIT" append_cmd 'journalctl --user -u openclaw-gateway.service --since "2026-02-21 20:30:00" --until "2026-02-21 20:50:00" --no-pager || true' append_cmd 'grep -RIn --color=never -E "tg-mlws9pj6-002|Gateway logs contain details" ~/.local/state/openclaw 2>/dev/null || true'  # Phase 7 verification per acceptance criteria {   echo '## Phase 7 Verification'   echo } >> "$AUDIT" append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'pgrep -af "vllm|openai.api_server|api_server" || true' append_cmd 'bash -lc "~/bin/python-env-audit.sh" || true' append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'systemctl --user restart openclaw-gateway.service' append_cmd 'sleep 2; systemctl --user status openclaw-gateway.service --no-pager | sed -n "1,80p"' append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'pgrep -af "vllm serve|openai.api_server|local-assistant" || true'  # extra: ensure no timer mentions openclaw-vllm append_cmd 'systemctl --user list-timers --all | grep -i -E "openclaw|vllm|llm|audit" || true'  echo done
16653 bash -lc pgrep -af "vllm serve|openai.api_server|local-assistant" || true
```

```bash
systemctl --user list-timers --all | grep -i -E "openclaw|vllm|llm|audit" || true
```

```text
```

## Root Cause Conclusion

- Case classification: **B** (single listener on `127.0.0.1:8001`, plus a competing second vLLM process in restart/fail loop).
- Confirmed launcher conflict:
  - System unit `vllm-assistant.service` (enabled) owns `:8001` and runs `local-assistant`.
  - User unit `openclaw-vllm.service` (was enabled with `Restart=always`) repeatedly attempted the same `local-assistant` on `:8001` and failed/restarted.
- `~/bin/python-env-audit.sh` is observational only; it does not start or restart vLLM.
- Cron entry exists for `python-env-audit.sh` at `45 3 * * *`, but script output confirms no vLLM side effects.
- Time certainty note: no claim is made that a user was active at 03:45. In captured logs, duplicate-launcher evidence is explicit around **2026-02-22 06:52 AEST** (openclaw-vllm restart loop) and listener ownership around **2026-02-22 06:35 AEST** (`vllm-assistant`).

## Fix Description

- Enforced singleton owner by disabling the competing user unit:
  - Kept: `vllm-assistant.service` (system).
  - Disabled/stopped: `openclaw-vllm.service` (user).
- This removes automatic recurrence via user systemd restart loops while preserving active service on `:8001`.

## Phase 4 Containment Note

- Phase 4 hard kill was **not** executed because there were not two simultaneous binders on `:8001` during containment checks.
- Listener ownership remained singular (`pid=3285`, `vllm-assistant.service`).

## Rollback

1. Revert git commit in repo:
   - `git revert <commit_sha>`
2. Re-enable prior user vLLM service (if intentionally desired):
   - `systemctl --user unmask openclaw-vllm.service || true`
   - `systemctl --user enable --now openclaw-vllm.service`
3. To switch ownership from system to user unit (not recommended unless deliberate):
   - `sudo systemctl disable --now vllm-assistant.service`
   - `systemctl --user enable --now openclaw-vllm.service`

## Reproduction / Verification Commands

```bash
ss -ltnp | grep -E '(:8001)\b' || true
pgrep -af 'vllm|openai.api_server|api_server' || true
bash -lc '~/bin/python-env-audit.sh' || true
systemctl --user restart openclaw-gateway.service
ss -ltnp | grep -E '(:8001)\b' || true
pgrep -af 'vllm serve|openai.api_server|local-assistant' || true
```
