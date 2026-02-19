# Source UI - Ubuntu Desktop App

A standalone desktop application for OpenClaw's Source UI.

## Quick Start

```bash
# Install dependencies
cd /home/jeebs/src/clawd/workspace/source-ui
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
python3 app.py --port 18990
```

Then open http://localhost:18990 in your browser.
