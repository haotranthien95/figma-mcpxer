# figma-mcpxer

Remote MCP server that exposes the full Figma API as structured tools for LLM agents.

Connect any MCP-compatible client (Claude Desktop, Cursor, custom agents) over HTTP/SSE and use it to read designs, extract tokens, inspect components, and generate pixel-accurate UI code that matches Figma exactly.

**We build only the server.** Clients connect remotely — no local install required by the client.

---

## Prerequisites

- Python 3.12+ (local) **or** Docker + Docker Compose
- A Figma Personal Access Token — get one at **Figma → Settings → Personal Access Tokens**

---

## Quick Start

### Option A — Local (Python)

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd figma-mcpxer

# 2. Create a virtual environment
python3.12 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Configure environment
cp .env.example .env
# Edit .env and set FIGMA_ACCESS_TOKEN=your-token

# 5. Start the server
python -m figma_mcpxer
```

Server starts at **http://localhost:8000**

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness check |
| `GET /sse` | MCP client connect here |
| `GET /metrics` | Prometheus metrics |
| `POST /webhooks/figma` | Figma webhook receiver |

---

### Option B — Docker (recommended)

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env and set FIGMA_ACCESS_TOKEN=your-token

# 2. Build and start
docker-compose up --build

# Stop
docker-compose down
```

The server runs at **http://localhost:8000** with hot-reload (source is mounted as a volume in dev mode).

---

### Option C — Docker Production

```bash
# Uses Redis for shared cache, resource limits, and JSON structured logs
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f figma-mcp

# Stop
docker-compose -f docker-compose.prod.yml down
```

Production stack includes:
- **figma-mcp** — the MCP server (1 CPU / 512 MB limit, `restart: always`)
- **redis** — shared TTL cache (128 MB, `allkeys-lru` eviction)

---

## Connect an MCP Client

Once the server is running, point your MCP client at the SSE endpoint.

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "figma": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

Restart Claude Desktop. The Figma tools will appear automatically.

### Cursor / other clients

Set the MCP server URL to `http://localhost:8000/sse` in your client's MCP settings.

### With authentication

Set `MCP_AUTH_TOKEN` in `.env`, then clients must send:

```
Authorization: Bearer <your-token>
```

---

## Environment Variables

Copy `.env.example` to `.env` and adjust as needed.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FIGMA_ACCESS_TOKEN` | **Yes** | — | Figma Personal Access Token |
| `FIGMA_API_BASE_URL` | No | `https://api.figma.com/v1` | Override for proxies/testing |
| `MCP_HOST` | No | `0.0.0.0` | Bind host |
| `MCP_PORT` | No | `8000` | Bind port |
| `MCP_AUTH_TOKEN` | No | — | Require clients to send `Bearer <token>` |
| `CACHE_TTL_SECONDS` | No | `300` | Figma response cache TTL in seconds |
| `REDIS_URL` | No | — | Enable Redis cache (e.g. `redis://localhost:6379/0`) |
| `FIGMA_WEBHOOK_PASSCODE` | No | — | Secret validated on webhook deliveries |
| `RATE_LIMIT_RPS` | No | `60` | Max requests/second per client IP (0 = off) |
| `LOG_FORMAT` | No | `text` | `json` for structured production logs |
| `LOG_LEVEL` | No | `INFO` | Logging level |

---

## Available Tools (28 total)

| Phase | Tools |
|-------|-------|
| File & Nodes | `figma_get_file`, `figma_list_pages`, `figma_get_node`, `figma_get_nodes`, `figma_search_nodes` |
| Design Tokens | `figma_get_colors`, `figma_get_typography`, `figma_get_spacing`, `figma_get_effects`, `figma_get_grids`, `figma_get_variables` |
| Components | `figma_get_components`, `figma_get_component_sets`, `figma_get_styles`, `figma_export_image`, `figma_export_images`, `figma_get_images` |
| Layout | `figma_get_auto_layout`, `figma_get_constraints`, `figma_get_absolute_bounds`, `figma_get_fills` |
| Code Gen | `figma_get_css`, `figma_describe_component`, `figma_get_design_tokens_json` |
| Collaboration | `figma_get_comments`, `figma_post_comment`, `figma_get_versions`, `figma_get_team_components`, `figma_get_projects` |
| Webhooks | `figma_create_webhook`, `figma_list_webhooks`, `figma_delete_webhook` |

---

## Development

```bash
# Lint
ruff check src/

# Type check
mypy src/

# Run all unit tests
pytest tests/unit/ -v

# Run tests with coverage report
pytest --cov=src --cov-report=term-missing

# Run a single test file
pytest tests/unit/test_phase7_tools.py -v

# Install with Redis support (optional)
pip install -e ".[redis]"
```

### Project Structure

```
src/figma_mcpxer/
├── server.py          # ASGI app — routes, middleware, lifespan
├── config.py          # All env vars via pydantic-settings
├── metrics.py         # Prometheus counters/histograms
├── tools/             # One file per tool group, auto-registered
├── figma/client.py    # Single httpx client — only Figma API caller
├── cache/             # In-memory (default) or Redis store
├── webhooks/          # Figma webhook event handler
└── middleware/        # Rate limiting, structured JSON logging
```

### Adding a New Tool

1. Create `src/figma_mcpxer/tools/my_tools.py`
2. Define `async def _handle_*(arguments, client, cache)` handler
3. Call `register(types.Tool(...), _handle_*)` at module level
4. Import the module in `tools/registry.py` inside `_load_all_tool_modules()`

### Webhook Setup

To receive real-time `FILE_UPDATE` events from Figma:

```bash
# 1. Set your passcode in .env
FIGMA_WEBHOOK_PASSCODE=my-secret

# 2. Expose the server publicly (ngrok for local dev)
ngrok http 8000

# 3. Register the webhook via MCP tool
figma_create_webhook(
  team_id="your-team-id",
  endpoint="https://abc.ngrok.io/webhooks/figma",
  passcode="my-secret"
)
```

When Figma sends a `FILE_UPDATE` event the server automatically invalidates the cache for that file — the next tool call fetches fresh data.

---

## Contributing

See [CLAUDE.md](CLAUDE.md) for architecture decisions and the feature roadmap.

Commit format: `type(scope): description` — types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
