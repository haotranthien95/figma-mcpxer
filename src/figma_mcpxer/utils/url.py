from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

# Matches /design/KEY/... or /file/KEY/... or /make/KEY/...
_FILE_KEY_RE = re.compile(r"figma\.com/(?:design|file|make)/([A-Za-z0-9]+)")


def extract_file_key(url_or_key: str) -> str:
    """Return the Figma file key from a URL or pass through a bare key.

    Handles all common Figma URL formats:
      https://www.figma.com/design/AbCd.../My-File?node-id=...
      https://www.figma.com/file/AbCd.../My-File
    """
    if "figma.com" not in url_or_key:
        # Assume it's already a raw key
        return url_or_key.strip()
    match = _FILE_KEY_RE.search(url_or_key)
    if not match:
        raise ValueError(f"Cannot extract file key from URL: {url_or_key!r}")
    return match.group(1)


def extract_node_id(url: str) -> str | None:
    """Extract the node ID from a Figma URL query string.

    Returns the ID in colon-separated format (e.g. '1234:5678'),
    normalising the dash-separated variant Figma uses in URLs.
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    raw = params.get("node-id", [None])[0]
    return normalize_node_id(raw) if raw else None


def normalize_node_id(node_id: str) -> str:
    """Normalize a Figma node ID to colon-separated format (API canonical form).

    Figma URLs use dashes ('1234-5678') but the REST API uses colons ('1234:5678').
    """
    return node_id.replace("-", ":")
