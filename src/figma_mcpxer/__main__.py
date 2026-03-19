from __future__ import annotations

import logging

import uvicorn

from figma_mcpxer.config import get_settings
from figma_mcpxer.server import create_app


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())

    app = create_app(settings)
    uvicorn.run(
        app,
        host=settings.mcp_host,
        port=settings.mcp_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
