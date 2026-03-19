"""Prometheus metrics for Phase 9 production observability.

Metrics exposed at GET /metrics in the Prometheus text format.
Import this module early (server.py does so) so counters exist before
the first request arrives.

Tracked:
  figma_mcp_requests_total        — tool calls by name and status
  figma_mcp_request_duration_ms   — tool call duration histogram
  figma_mcp_http_requests_total   — HTTP requests by method/path/status
  figma_mcp_cache_operations_total — cache get/set/delete operations
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

# ------------------------------------------------------------------
# MCP Tool metrics
# ------------------------------------------------------------------

TOOL_CALLS = Counter(
    "figma_mcp_tool_calls_total",
    "Total MCP tool calls by tool name and outcome",
    ["tool", "status"],  # status: success | error
)

TOOL_DURATION = Histogram(
    "figma_mcp_tool_duration_ms",
    "MCP tool call duration in milliseconds",
    ["tool"],
    buckets=[10, 50, 100, 250, 500, 1000, 2500, 5000],
)

# ------------------------------------------------------------------
# HTTP request metrics
# ------------------------------------------------------------------

HTTP_REQUESTS = Counter(
    "figma_mcp_http_requests_total",
    "Total HTTP requests by method, path, and status code",
    ["method", "path", "status"],
)

# ------------------------------------------------------------------
# Cache metrics
# ------------------------------------------------------------------

CACHE_OPS = Counter(
    "figma_mcp_cache_operations_total",
    "Cache operations by type and result",
    ["operation", "result"],  # operation: get|set|delete, result: hit|miss|ok
)
