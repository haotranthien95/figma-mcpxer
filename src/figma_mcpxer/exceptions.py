from __future__ import annotations


class FigmaAPIError(Exception):
    """Raised when the Figma REST API returns an error response."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"Figma API error {status_code}: {message}")
        self.status_code = status_code
        self.message = message


class FigmaNotFoundError(FigmaAPIError):
    """Raised when the requested Figma resource does not exist."""

    def __init__(self, resource: str = "Resource") -> None:
        super().__init__(404, f"{resource} not found")


class FigmaAuthError(FigmaAPIError):
    """Raised when the Figma access token is invalid or missing."""

    def __init__(self) -> None:
        super().__init__(403, "Invalid or missing Figma access token")


class FigmaRateLimitError(FigmaAPIError):
    """Raised when the Figma API rate limit is exceeded."""

    def __init__(self) -> None:
        super().__init__(429, "Figma API rate limit exceeded — retry after a moment")


class MCPAuthError(Exception):
    """Raised when an MCP client fails server-level authentication."""

    def __init__(self) -> None:
        super().__init__("Invalid or missing MCP authentication token")


class ToolInputError(Exception):
    """Raised when an MCP tool receives invalid arguments."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Invalid tool input: {message}")
