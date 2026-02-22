# Local Exec Systemd User Units

This repo ships templates for user-scoped services:
- `openclaw-local-exec-worker.service`
- `vllm-local-exec.service`

Install templates into user systemd dir:

```bash
cd <repo>
bash scripts/local_exec_plane.sh install-units
systemctl --user daemon-reload
```

Create env file (no secrets in repo):

```bash
mkdir -p ~/.config/openclaw
cat > ~/.config/openclaw/local_exec.env <<'EOF'
MODEL_ID=Qwen/Qwen2.5-Coder-7B-Instruct
VLLM_API_KEY=replace-with-local-secret
EOF
chmod 600 ~/.config/openclaw/local_exec.env
```

Enable/start only when intended:

```bash
bash scripts/local_exec_plane.sh enable-vllm
```

Logs:

```bash
journalctl --user -u vllm-local-exec.service -n 200 --no-pager
```
