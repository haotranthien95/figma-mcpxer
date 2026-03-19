# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

`figma-mcpxer` is a **remote MCP server** (hosted in Docker) that exposes the full Figma API as structured MCP tools. Any MCP-compatible client (Claude Desktop, Cursor, custom agents) can connect to it over HTTP/SSE and use it to read designs, extract tokens, inspect components, and generate pixel-accurate UI code that matches Figma exactly.

**We build only the server. Clients connect remotely — no stdio, no local install required by the client.**

---

## Feature Roadmap

Progress is tracked here. Mark `[x]` when a feature is complete and tested.

### Phase 0 — Project Bootstrap ✅
- [x] `pyproject.toml` with all dependencies declared
- [x] `src/figma_mcpxer/` package skeleton created
- [x] `Dockerfile` + `docker-compose.yml` working (`docker-compose up` starts server)
- [x] `.env.example` committed
- [x] Health check endpoint responding at `GET /health`
- [x] `ruff`, `mypy`, `pytest` all pass in CI

### Phase 1 — Core MCP Infrastructure ✅
- [x] HTTP + SSE transport running (not stdio) so remote clients can connect
- [x] `GET /sse` endpoint for MCP client handshake
- [x] `POST /messages` endpoint for MCP tool calls
- [x] `list_tools` returns all registered tools
- [x] Auth middleware: clients pass `Authorization: Bearer <token>` or server-side `FIGMA_ACCESS_TOKEN` is injected automatically
- [x] Structured error responses (MCP-compliant, not raw 500s)

### Phase 2 — File & Node Tools ✅
- [x] `figma_get_file` — full file tree (name, pages, nodes hierarchy)
- [x] `figma_get_node` — single node by ID with all properties
- [x] `figma_get_nodes` — batch fetch multiple nodes in one call
- [x] `figma_list_pages` — list pages in a file with node counts
- [x] `figma_search_nodes` — search nodes by name, type, or property value

### Phase 3 — Design Token Tools (required for pixel-accurate UI)
- [x] `figma_get_colors` — all color styles with hex, rgba, and usage context
- [x] `figma_get_typography` — all text styles (font family, size, weight, line-height, letter-spacing)
- [x] `figma_get_spacing` — spacing/padding/gap values extracted from auto-layout nodes
- [x] `figma_get_effects` — shadows, blurs, and overlays as CSS-ready values
- [x] `figma_get_variables` — Figma Variables (collections, modes, resolved values)
- [x] `figma_get_grids` — layout grids (columns, rows, gutters)

### Phase 4 — Component & Asset Tools
- [x] `figma_get_components` — all local components with props and variants
- [x] `figma_get_component_sets` — component sets and their variant properties
- [x] `figma_get_styles` — all published styles (fill, stroke, text, effect, grid)
- [x] `figma_export_image` — export a node as PNG/SVG/PDF at specified scale
- [x] `figma_export_images` — batch export multiple nodes
- [x] `figma_get_images` — resolve image fill references to URLs

### Phase 5 — Layout & Structure Tools (for accurate CSS generation)
- [x] `figma_get_auto_layout` — auto-layout properties per node (direction, gap, padding, alignment, sizing mode)
- [x] `figma_get_constraints` — node constraints (horizontal/vertical) for responsive behaviour
- [x] `figma_get_absolute_bounds` — absolute x/y/width/height for every node
- [x] `figma_get_fills` — all fill types (solid, gradient, image) with positions and opacity

### Phase 6 — Code Generation Hint Tools
- [x] `figma_get_css` — CSS properties for a node computed by Figma (uses Figma's own CSS export)
- [x] `figma_describe_component` — structured description of a component: slots, variants, required props, design intent
- [x] `figma_get_design_tokens_json` — full design token export in W3C Design Token format

### Phase 7 — Collaboration & Metadata Tools
- [ ] `figma_get_comments` — all comments on a file or node
- [ ] `figma_post_comment` — post a comment on a node
- [ ] `figma_get_versions` — file version history
- [ ] `figma_get_team_components` — list components published from a team library
- [ ] `figma_get_projects` — list projects for a team

### Phase 8 — Webhooks & Real-time (advanced)
- [ ] Figma webhook receiver for `FILE_UPDATE` events
- [ ] Invalidate and re-fetch cached data on webhook trigger
- [ ] Push update notification to connected SSE clients

### Phase 9 — Production Hardening
- [ ] Response caching layer (Redis or in-memory TTL cache) to reduce Figma API rate-limit exposure
- [ ] Rate limiter on incoming MCP requests
- [ ] Structured JSON logging with request IDs
- [ ] Prometheus metrics endpoint (`/metrics`) — request count, latency, cache hit rate
- [ ] Docker image published to registry with version tags
- [ ] `docker-compose.prod.yml` with resource limits and restart policies

---

## Architecture

```
src/figma_mcpxer/
├── server.py          # FastAPI app + MCP SSE/HTTP transport mount
├── config.py          # pydantic-settings: all env vars loaded here
├── exceptions.py      # Custom exception hierarchy
├── tools/             # One file per tool group (file.py, tokens.py, components.py, ...)
│   └── registry.py    # Imports all tools and registers them with the MCP server
├── figma/
│   ├── client.py      # Single async httpx client — only place that calls Figma REST API
│   └── models.py      # Pydantic v2 models for every Figma API response shape
├── cache/
│   └── store.py       # TTL cache abstraction (memory for dev, Redis for prod)
└── utils/
    ├── url.py         # Figma URL parsing (fileKey, nodeId extraction)
    ├── css.py         # Figma → CSS property converters
    └── tokens.py      # Design token formatters (W3C, Tailwind, CSS vars)

tests/
├── unit/              # Mocked figma/client.py responses
├── integration/       # Real Figma API (requires FIGMA_TEST_FILE_KEY)
└── conftest.py        # Shared fixtures
```

**Key design rules:**
- `tools/` files define MCP tool schemas and delegate to `figma/client.py` — no HTTP calls anywhere else
- `server.py` mounts MCP over SSE/HTTP (not stdio) so Docker-hosted server is reachable by remote clients
- All config via `config.py` — never `os.getenv()` scattered in code
- MCP tool `inputSchema` must have `"additionalProperties": false`
- Files < 300 lines; split by responsibility if longer
- `utils/` functions are pure (no I/O, no side effects)

## Transport: HTTP + SSE (not stdio)

The server uses `mcp` with Starlette/FastAPI SSE transport so any remote client can connect without installing anything locally:

```python
# server.py — remote-capable transport
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Mount, Route

transport = SseServerTransport("/messages")

async def handle_sse(request):
    async with transport.connect_sse(request.scope, request.receive, request._send) as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())

starlette_app = Starlette(routes=[
    Route("/sse", endpoint=handle_sse),
    Mount("/messages", app=transport.handle_post_message),
    Route("/health", endpoint=health_check),
])
```

**Client connection** (example `claude_desktop_config.json` snippet):
```json
{
  "mcpServers": {
    "figma": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

---

## Docker

```bash
# Development
docker-compose up --build

# Production
docker-compose -f docker-compose.prod.yml up -d

# Rebuild after dependency changes
docker-compose build --no-cache
```

The container exposes **port 8000**. Map it as needed in `docker-compose.yml`.

**`Dockerfile` requirements:**
- Multi-stage build (`builder` → `runtime`)
- Non-root user
- Pin base image version (e.g. `python:3.12-slim`)
- `HEALTHCHECK` via `curl http://localhost:8000/health`

---

## Development Commands

```bash
# Install dependencies (dev)
pip install -e ".[dev]"

# Run the MCP server locally (without Docker)
python -m figma_mcpxer

# Lint
ruff check src/

# Type check
mypy src/

# Run all tests
pytest

# Run a single test file
pytest tests/unit/test_figma_client.py -v

# Run tests with coverage
pytest --cov=src --cov-report=term-missing
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FIGMA_ACCESS_TOKEN` | Yes | — | Personal access token from Figma account settings |
| `FIGMA_API_BASE_URL` | No | `https://api.figma.com/v1` | Override for testing/proxies |
| `MCP_HOST` | No | `0.0.0.0` | Host the SSE server binds to |
| `MCP_PORT` | No | `8000` | Port the SSE server listens on |
| `CACHE_TTL_SECONDS` | No | `300` | TTL for cached Figma responses |
| `REDIS_URL` | No | — | If set, use Redis for caching; otherwise in-memory |
| `FIGMA_TEST_FILE_KEY` | Integration tests only | — | Figma file key used in integration test suite |

Copy `.env.example` to `.env` before running locally.

---

## Coding Standards

- **Type hints**: Always on all params and return types; `X | None` not `Optional[X]`; `from __future__ import annotations` at top
- **Functions**: Max 20 lines, one responsibility; keyword args when > 3 params
- **Configuration**: pydantic-settings singleton with `@lru_cache` — never `os.getenv()`
- **Error handling**: Custom exceptions in `exceptions.py`; never bare `except:`; `logging` not `print()`
- **Async**: `asyncio.sleep()` not `time.sleep()` in async code; single shared `httpx.AsyncClient` (do not create per-request)
- **Naming**: `snake_case` functions/vars, `PascalCase` classes, `UPPER_SNAKE_CASE` constants, `_single_underscore` private
- **Commit messages**: `type(scope): description` — types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

---

## Testing Approach

- **Unit tests** (`tests/unit/`): Mock `figma/client.py`; test tool schemas, output formatting, CSS converters, token formatters
- **Integration tests** (`tests/integration/`): Hit real Figma API using `FIGMA_TEST_FILE_KEY`
- Fixtures in `tests/conftest.py` — shared mock client and sample Figma response payloads
- Test naming: `test_{what}_{condition}_{expected_result}`
- Use `pytest-asyncio` for async tests; no shared mutable state between tests

**Coverage targets:**

| Layer | Minimum |
|-------|---------|
| `tools/` | 80% |
| `figma/` | 60% |
| `utils/` | 90% |
