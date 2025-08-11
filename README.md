# Desktop Assistant (Electron + React + Python)

A cross-platform desktop automation assistant that combines an Electron (Node + React) desktop app with a Python automation/runtime service. It can analyze your live desktop screen with computer vision + OCR, discover actionable UI elements, enhance LLM prompts with real-time context, and execute actions using element-aware clicks, typing, keyboard shortcuts, and coordinate fallbacks. It also includes specialized web browser automation for Chrome/Firefox/Edge on Windows via UI Automation.

---

## Overview

- Desktop app built with Electron (main process) + React/Vite renderer
- Python backend providing:
  - Host screen computer-vision UI element discovery (no Docker required)
  - OCR-based text extraction (Tesseract, optional)
  - Screenshot capture (with or without grid overlay)
  - Action execution (click/type/press/scroll)
  - Web browser automation (Windows UI Automation)
  - OpenAI GPT integration (chat + vision)
- LLM prompt enhancement: real-time UI context bundled alongside screenshots so the LLM can act on named elements rather than blind coordinates

---

## Key Features

- Real-time host screen UI detection (CV + OCR)
  - Detects buttons, text inputs, links, and other clickable regions
  - Confidence scores per element; top elements summarized
  - Optional debug visualization image with bounding boxes and labels
- Multi-source UI context for LLMs
  - Host screen elements (highest priority)
  - Browser UI + web content structure (Windows)
  - Desktop UI and coordinate fallback
- Action execution
  - Element-aware clicks when a matching element is found
  - Coordinate-based clicks as fallback
  - Typing text input
  - Key presses (Enter, Tab, Escape, Space)
  - Scrolling up/down
- Web browser automation (Windows)
  - Discovers browser windows, tabs, address bars, navigation controls, and web content areas
  - Summaries and natural-language element search (e.g., "address bar", "back button")
- GPT integration
  - Text chat via `gpt-4o-mini`
  - Vision chat using `gpt-4o` with high-detail screenshots
- Logging & observability
  - In-memory action logs with retrieval and clear APIs
- Cross-platform CV pipeline
  - Screen capture via `mss` with fallback to `PIL.ImageGrab`
  - Works on Windows/macOS/Linux for CV portions (browser UIAutomation is Windows-centric)

---

## Architecture

- Frontend: React + Vite (`src/`)
- Desktop shell: Electron (see `electron/main.js`)
  - Main process creates the BrowserWindow loading the Vite dev server or built files
  - Renderer talks directly to Python HTTP APIs
- Automation backend: Python Flask service (`src-py/`)
  - Endpoints for screenshots, UI discovery/summaries, element search, action execution
  - GPT text/vision endpoints
  - Web browser discovery and summaries (Windows UI Automation)

Data flow (simplified):

1. User triggers automation or provides a goal
2. Renderer (React) calls Python service to capture screenshot + discover host screen elements
3. Renderer combines: screenshot + host screen elements + (optional) browser/desktop context → crafts enhanced LLM prompt
4. LLM responds with element-aware actions → renderer requests Python to execute (element-based preferred; fallback to coordinates)

For historical Tauri integration notes, see `LLM_INTEGRATION_SUMMARY.md`.

---

## Capabilities Matrix

- Host Screen CV + OCR: Windows, macOS, Linux
- Web Browser UI Automation: Windows (uses `uiautomation`)
- Action Types:
  - Click (element-aware or coordinates)
  - Type text
  - Key presses (Enter, Tab, Escape, Space)
  - Scroll up/down
- LLM Models:
  - Text: `gpt-4o-mini`
  - Vision: `gpt-4o`

---

## Python Service API (Quick Reference)

Base: `http://localhost:5000`

- General
  - GET `/` → service info and feature list
  - GET `/health` → health + OpenAI configured
- Screenshots
  - GET `/screenshot` → base64 PNG
  - GET `/screenshot-with-grid` → base64 PNG, grid overlay with labeled coordinates
- LLM
  - POST `/chat` → `{ message }` → GPT text response
  - POST `/chat-vision` → `{ message, image_data }` → GPT vision response
- UI Automation (Host Screen CV)
  - GET `/discover-ui-elements` → list of elements with positions and confidence
  - GET `/ui-summary` → actionable summary (counts + top elements)
  - POST `/find-ui-element` → `{ description }` → best matching element
  - POST `/execute-action` → `{ instruction }` (e.g., `Click (x, y)`, `Type "text"`, `Press Enter`)
- Browser Automation (Windows)
  - GET `/discover-browser-elements` → categorized browser data (windows, tabs, address bars, navigation, web content, clickable/typable)
  - GET `/browser-summary` → summarized browser context
  - POST `/find-browser-element` → `{ description, browser? }` → best match in browser context
- Logging
  - GET `/action-logs` → recent in-memory logs
  - POST `/log-action` → manually append a log entry
  - POST `/clear-logs` → clear logs
- Utilities
  - GET `/test-host-screen` → verify host screen capture works

---

## Notable Modules

- `src-py/ui_element_discovery.py`
  - Captures the live screen and detects UI elements using OpenCV + OCR
  - Provides summarization, element search, and debug visualization
- `src-py/web_browser_automation.py` (Windows)
  - Discovers browser window elements (tabs, address bar, nav, content)
  - Groups and summarizes elements; supports natural language lookup
- `src-py/main.py`
  - Flask app exposing HTTP endpoints for screenshots, discovery, GPT, and action execution
- `LLM_INTEGRATION_SUMMARY.md`
  - Historical documentation when the app used Tauri/Rust. Now the renderer orchestrates Electron + Python HTTP directly

---

## Project Structure (high level)

```
Desktop_Agent/
  README.md
  LLM_INTEGRATION_SUMMARY.md
  UI_AUTOMATION_BRIDGE.md
  SCREENENV_MIGRATION_README.md
  src/                # React frontend (Vite + TS)
  electron/           # Electron main process (this folder will be created)
  src-py/             # Python Flask automation service
  test_*.py           # Demo & test scripts for components
```

---

## Setup

Prerequisites:

- Node.js 18+
- Electron runtime (installed via devDependencies)
- Python 3.9+
- Pip packages: `pip install -r src-py/requirements.txt`
- Optional for OCR: Tesseract
  - Windows: install from releases and ensure `tesseract` is on PATH
  - macOS: `brew install tesseract`
  - Linux: `apt-get install tesseract-ocr`
- OpenAI API key: create `.env` with `OPENAI_API_KEY=...` (can place at project root or `src-py/.env`)

Install frontend deps:

```
   npm install
```

Install Python deps:

```
pip install -r src-py/requirements.txt
```

---

## Running

Option A: Run Python service + Electron app separately (recommended for development)

1. Start Python backend:

```
python src-py/main.py
```

2. In another terminal, start the Electron app:

```
npm run dev
```

Option B: Start renderer then Electron separately

- Terminal 1: `npm run dev:renderer`
- Terminal 2: `npm run dev:electron`

Build:

```
npm run build
```

---

## Usage Examples

- Take screenshot: GET `http://localhost:5000/screenshot`
- Get UI summary for LLM: GET `http://localhost:5000/ui-summary`
- Find an element by description: POST `/find-ui-element` with `{ "description": "Search" }`
- Execute an action:
  - `{"instruction": "Click (120, 300)"}`
  - `{"instruction": "Type \"hello world\""}`
  - `{"instruction": "Press Enter"}`
- Vision chat: POST `/chat-vision` with a base64 PNG from `/screenshot`

---

## Demos & Tests

Run targeted demos/tests from the project root:

- Host screen UI detection (no Docker required):

```
python test_host_screen_ui_bridge.py
```

- Integration test and prompt generation:

```
python test_integration.py
```

- Browser automation demo (Windows):

```
python test_browser_automation.py
```

- Legacy/UI bridge demos (for reference):

```
python test_ui_bridge.py
python test_screenenv_ui_bridge.py
```

These scripts print summaries to the console and write artifacts like `integration_test_prompt.txt` and `browser_automation_results.json`.

---

## Configuration Notes

- Electron main process configures the BrowserWindow titled "Desktop Assistant"
- Python service loads `.env` from several common locations; verify your `OPENAI_API_KEY` is discoverable
- Browser automation requires an open browser window and currently targets Windows via `uiautomation`

---

## Limitations

- Browser UI automation is Windows-centric (uses Windows UI Automation). CV-based host screen detection works cross-platform
- OCR quality depends on Tesseract availability and on-screen text clarity
- Element detection uses classical CV heuristics; confidence scores help prioritize, but results vary by UI/theme

---

## Roadmap

- Element caching and debouncing for performance
- Configurable confidence thresholds
- Grouping elements into higher-level structures (forms, dialogs)
- ML-based element recognition
- Deeper integration with accessibility APIs for robust cross-platform element discovery

---

## Safety & Permissions

- The app can control mouse/keyboard via `pyautogui`; OS permissions may be required (especially on macOS)
- Use with caution; test on non-critical windows first

---

## License

Specify a license here (e.g., MIT). If omitted, the repository defaults to "All rights reserved".
