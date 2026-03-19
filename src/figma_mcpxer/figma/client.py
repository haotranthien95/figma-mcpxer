from __future__ import annotations

import logging
from typing import Any

import httpx

from figma_mcpxer.exceptions import (
    FigmaAPIError,
    FigmaAuthError,
    FigmaNotFoundError,
    FigmaRateLimitError,
)

logger = logging.getLogger(__name__)

# Single shared client — do not instantiate httpx.AsyncClient per request
_STATUS_HANDLERS: dict[int, type[FigmaAPIError]] = {
    403: FigmaAuthError,
    404: FigmaNotFoundError,
    429: FigmaRateLimitError,
}

# Figma Webhooks API uses v2 — different base path from the rest of the API
_FIGMA_V2_BASE = "https://api.figma.com/v2"


def _raise_for_figma_error(response: httpx.Response) -> None:
    """Convert non-2xx Figma API responses into typed exceptions."""
    if response.is_success:
        return
    exc_class = _STATUS_HANDLERS.get(response.status_code)
    known = (FigmaAuthError, FigmaNotFoundError, FigmaRateLimitError)
    if exc_class and issubclass(exc_class, known):
        raise exc_class()
    body = response.text[:200]
    raise FigmaAPIError(response.status_code, body)


class FigmaClient:
    """Async HTTP client for the Figma REST API.

    This is the only place in the codebase that calls Figma's API.
    Instantiate once per server lifespan and reuse across all requests.
    """

    def __init__(self, access_token: str, base_url: str = "https://api.figma.com/v1") -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-Figma-Token": access_token},
            timeout=httpx.Timeout(30.0),
        )

    async def get_file(
        self,
        file_key: str,
        *,
        depth: int | None = None,
    ) -> dict[str, Any]:
        """Fetch a Figma file. depth limits node tree depth (None = full tree)."""
        params: dict[str, Any] = {}
        if depth is not None:
            params["depth"] = depth
        logger.debug("GET /files/%s depth=%s", file_key, depth)
        response = await self._http.get(f"/files/{file_key}", params=params)
        _raise_for_figma_error(response)
        return response.json()  # type: ignore[no-any-return]

    async def get_file_nodes(
        self,
        file_key: str,
        node_ids: list[str],
    ) -> dict[str, Any]:
        """Fetch specific nodes from a file by ID."""
        ids_param = ",".join(node_ids)
        logger.debug("GET /files/%s/nodes ids=%s", file_key, ids_param)
        response = await self._http.get(
            f"/files/{file_key}/nodes", params={"ids": ids_param}
        )
        _raise_for_figma_error(response)
        return response.json()  # type: ignore[no-any-return]

    async def get_local_variables(self, file_key: str) -> dict[str, Any]:
        """Fetch Figma Variables defined in the file (requires Figma Professional+)."""
        logger.debug("GET /files/%s/variables/local", file_key)
        response = await self._http.get(f"/files/{file_key}/variables/local")
        _raise_for_figma_error(response)
        return response.json()  # type: ignore[no-any-return]

    async def export_images(
        self,
        file_key: str,
        node_ids: list[str],
        *,
        format: str = "png",
        scale: float = 1.0,
        use_absolute_bounds: bool = False,
    ) -> dict[str, Any]:
        """Render nodes as images. Returns {node_id: image_url | null}.

        Endpoint is /images/{file_key}, not /files/{file_key}/images.
        """
        params: dict[str, Any] = {
            "ids": ",".join(node_ids),
            "format": format,
            "scale": scale,
        }
        if use_absolute_bounds:
            params["use_absolute_bounds"] = "true"
        logger.debug("GET /images/%s format=%s ids=%s", file_key, format, node_ids)
        response = await self._http.get(f"/images/{file_key}", params=params)
        _raise_for_figma_error(response)
        return response.json()  # type: ignore[no-any-return]

    async def get_file_image_fills(self, file_key: str) -> dict[str, Any]:
        """Fetch CDN URLs for all image fill references in the file."""
        logger.debug("GET /files/%s/images", file_key)
        response = await self._http.get(f"/files/{file_key}/images")
        _raise_for_figma_error(response)
        return response.json()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------ #
    # Phase 7 — Collaboration & Metadata                                   #
    # ------------------------------------------------------------------ #

    async def get_file_comments(self, file_key: str) -> dict[str, Any]:
        """Fetch all comments on a Figma file."""
        logger.debug("GET /files/%s/comments", file_key)
        response = await self._http.get(f"/files/{file_key}/comments")
        _raise_for_figma_error(response)
        return response.json()  # type: ignore[no-any-return]

    async def post_file_comment(
        self,
        file_key: str,
        message: str,
        *,
        node_id: str | None = None,
        node_offset: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Post a comment on a Figma file, optionally pinned to a specific node."""
        body: dict[str, Any] = {"message": message}
        if node_id:
            # client_meta pins the comment to a node position
            client_meta: dict[str, Any] = {"node_id": node_id}
            if node_offset:
                client_meta["node_offset"] = node_offset
            body["client_meta"] = client_meta
        logger.debug("POST /files/%s/comments", file_key)
        response = await self._http.post(f"/files/{file_key}/comments", json=body)
        _raise_for_figma_error(response)
        return response.json()  # type: ignore[no-any-return]

    async def get_file_versions(self, file_key: str) -> dict[str, Any]:
        """Fetch the version history of a Figma file."""
        logger.debug("GET /files/%s/versions", file_key)
        response = await self._http.get(f"/files/{file_key}/versions")
        _raise_for_figma_error(response)
        return response.json()  # type: ignore[no-any-return]

    async def get_team_components(self, team_id: str) -> dict[str, Any]:
        """Fetch components published from a team library."""
        logger.debug("GET /teams/%s/components", team_id)
        response = await self._http.get(f"/teams/{team_id}/components")
        _raise_for_figma_error(response)
        return response.json()  # type: ignore[no-any-return]

    async def get_team_projects(self, team_id: str) -> dict[str, Any]:
        """List all projects for a Figma team."""
        logger.debug("GET /teams/%s/projects", team_id)
        response = await self._http.get(f"/teams/{team_id}/projects")
        _raise_for_figma_error(response)
        return response.json()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------ #
    # Phase 8 — Webhook Management (Figma API v2)                          #
    # ------------------------------------------------------------------ #

    async def create_webhook(
        self,
        team_id: str,
        event_type: str,
        endpoint: str,
        passcode: str,
    ) -> dict[str, Any]:
        """Register a Figma webhook via the v2 API.

        Uses the absolute v2 URL because the client's base_url is v1.
        """
        body = {
            "event_type": event_type,
            "team_id": team_id,
            "endpoint": endpoint,
            "passcode": passcode,
        }
        logger.debug("POST %s/webhooks team=%s event=%s", _FIGMA_V2_BASE, team_id, event_type)
        response = await self._http.post(f"{_FIGMA_V2_BASE}/webhooks", json=body)
        _raise_for_figma_error(response)
        return response.json()  # type: ignore[no-any-return]

    async def list_webhooks(self, team_id: str) -> dict[str, Any]:
        """List webhooks registered for a Figma team."""
        logger.debug("GET %s/teams/%s/webhooks", _FIGMA_V2_BASE, team_id)
        response = await self._http.get(f"{_FIGMA_V2_BASE}/teams/{team_id}/webhooks")
        _raise_for_figma_error(response)
        return response.json()  # type: ignore[no-any-return]

    async def delete_webhook(self, webhook_id: str) -> dict[str, Any]:
        """Delete a webhook by ID."""
        logger.debug("DELETE %s/webhooks/%s", _FIGMA_V2_BASE, webhook_id)
        response = await self._http.delete(f"{_FIGMA_V2_BASE}/webhooks/{webhook_id}")
        _raise_for_figma_error(response)
        return response.json()  # type: ignore[no-any-return]

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> FigmaClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()
