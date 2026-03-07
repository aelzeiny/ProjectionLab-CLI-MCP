# projectionlab-mcp

An MCP server for [ProjectionLab](https://app.projectionlab.com) that exposes its [Plugin API](https://docs.projectionlab.com/plugins) as tools for AI assistants.

## Requirements

- Python 3.11+
- A ProjectionLab account with **Plugins enabled** (Account Settings → Plugins)

## Setup

```bash
pip install -e .
playwright install chromium
```

Copy `.env.example` to `.env` and fill in your credentials:

```env
PROJECTIONLAB_EMAIL=your@email.com
PROJECTIONLAB_PASSWORD=yourpassword
PROJECTIONLAB_API_KEY=your-plugin-api-key
```

The API key is found in ProjectionLab under **Account Settings → Plugins**.

## Running

### Production

The server launches its own headless browser, logs in, and exposes the MCP tools over stdio:

```bash
projectionlab-mcp
```

By default the browser is headless. Set `HEADLESS=false` in `.env` for a visible window.

### Dev mode

Dev mode shares a single visible browser between the MCP server and a browser automation tool (e.g. [browser-mcp](https://github.com/executeautomation/mcp-playwright)) via Chrome DevTools Protocol. This lets you watch what the server is doing in real time.

**1. Start the shared browser:**
```bash
CDP_PORT=9222 python launch_browser.py
```

**2. Start the MCP server pointing at it:**
```bash
CDP_PORT=9222 projectionlab-mcp
```

## Tools

| Tool | Description |
|------|-------------|
| `export_data` | Export all data (finances, plans, progress, settings) |
| `update_account` | Update an account in Current Finances by ID |
| `restore_current_finances` | Replace the Current Finances state |
| `restore_plans` | Replace all plans |
| `restore_progress` | Replace progress history |
| `restore_settings` | Replace settings |
| `validate_api_key` | Check that the configured API key is valid |

## Project structure

```
projectionlab_mcp/
    browser.py      # Playwright browser lifecycle and login
    plugin_api.py   # ProjectionLab Plugin API calls
    models.py       # Pydantic models for exported data
    server.py       # FastMCP tool definitions
launch_browser.py   # Dev-mode browser launcher
```
