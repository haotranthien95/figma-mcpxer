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

    # App
    debug: bool = False
    log_level: str = "INFO"

    # Integration testing only
    figma_test_file_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
