# Source UI - Ubuntu Desktop App

A standalone desktop application for OpenClaw's Source UI.

## Quick Start

```bash
# Install dependencies
cd workspace/source-ui
npm install

# Run in development mode
npm start
```

## Requirements

- Node.js 18+
- npm
- Python 3 (for backend)

## Features

- Native Ubuntu window with controls
- System tray integration
- Auto-starts backend
- Menu bar with shortcuts
- Trails heatmap backend endpoint: `GET /api/trails/heatmap`

## Trails heatmap panel

- Backend helper: `workspace/source-ui/api/trails.py`
- Panel loader stub: `workspace/source-ui/panels/trails_heatmap.js`
- Enable via `SOURCE_UI_HEATMAP=1` (default OFF under TACTI(C)-R master governance)

## Building a .deb package

```bash
npm run build
```

This creates a `.deb` package in `dist/`.

## Manual Run (without Electron)

If you just want to run the web interface:

```bash
cp .source-ui.env.example .source-ui.env
# Set OPENCLAW_TOKEN in .source-ui.env (local only, do not commit)
./run-source-ui.sh --host 127.0.0.1 --port 18990
```

Then open http://localhost:18990 in your browser.

## systemd user service (optional)

Use `source-ui.service` as a user unit template with an environment file:

```bash
mkdir -p ~/.config/openclaw ~/.config/systemd/user
cp workspace/source-ui/source-ui.service ~/.config/systemd/user/source-ui.service
cp workspace/source-ui/.source-ui.env.example ~/.config/openclaw/source-ui.env
$EDITOR ~/.config/openclaw/source-ui.env
systemctl --user daemon-reload
systemctl --user enable --now source-ui.service
```
