from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Figma API
    figma_access_token: str
    figma_api_base_url: str = "https://api.figma.com/v1"

    # MCP Server transport
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8000
    # If set, MCP clients must pass "Authorization: Bearer <mcp_auth_token>"
    mcp_auth_token: str | None = None

    # Cache
    cache_ttl_seconds: int = 300
    redis_url: str | None = None  # enables Redis cache when set

    # Phase 8 — Webhooks
    # Passcode that Figma must include in each webhook delivery.
    # Set this when registering the webhook via figma_create_webhook.
    figma_webhook_passcode: str | None = None

    # Phase 9 — Rate limiting
    # Maximum requests per second per client IP. 0 = disabled.
    rate_limit_rps: int = 60

    # Phase 9 — Logging format: "json" for structured production logs, "text" for dev
    log_format: str = "text"

    # App
    debug: bool = False
    log_level: str = "INFO"

    # Integration testing only
    figma_test_file_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
