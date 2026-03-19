# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

`figma-mcpxer` is a Python MCP (Model Context Protocol) server that exposes Figma API capabilities as tools for LLM agents (Claude and others). It enables AI tools to read Figma designs, inspect components, and interact with Figma files via MCP tool calls.

## Development Commands

> Commands below assume the project will use `pyproject.toml` + `uv` (or `pip`). Update this section once the project is bootstrapped.

```bash
# Install dependencies (dev)
pip install -e ".[dev]"

# Run the MCP server
python -m figma_mcpxer          # or: python src/main.py

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

## Architecture

The project follows a layered structure:

```
src/figma_mcpxer/
├── server.py          # MCP server entry point — registers tools, starts stdio transport
├── config.py          # Settings via pydantic-settings (FIGMA_TOKEN, etc.)
├── tools/             # One file per MCP tool (get_file, get_node, get_components, ...)
├── figma/             # Figma API client — thin wrapper over REST API
│   ├── client.py      # Async HTTP client (httpx)
│   └── models.py      # Pydantic models for Figma API responses
└── utils/             # Pure helpers (URL parsing, node traversal, etc.)
```

**Key design rules:**
- `tools/` files define MCP tool schemas and call into `figma/client.py` — no business logic in the tool layer
- `figma/client.py` is the only place that makes HTTP calls to the Figma API
- All configuration (API tokens, base URLs) comes from `config.py` via `pydantic-settings` — never `os.getenv()` scattered in code
- MCP tool `inputSchema` must include `"additionalProperties": false`

## MCP Server Pattern

```python
# server.py — canonical structure
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server("figma-mcpxer")

@server.list_tools()
async def list_tools() -> list[types.Tool]: ...

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]: ...

if __name__ == "__main__":
    import asyncio
    asyncio.run(stdio_server(server))
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `FIGMA_ACCESS_TOKEN` | Yes | Personal access token from Figma settings |
| `FIGMA_API_BASE_URL` | No | Defaults to `https://api.figma.com/v1` |

Copy `.env.example` to `.env` before running locally.

## Testing Approach

- **Unit tests** (`tests/unit/`): Test tools and utilities with mocked Figma client responses
- **Integration tests** (`tests/integration/`): Hit the real Figma API using a test file key (set `FIGMA_TEST_FILE_KEY` in `.env`)
- Fixtures live in `tests/conftest.py` — shared mock client and sample Figma response data
