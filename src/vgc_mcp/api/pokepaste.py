"""PokePaste API client for fetching teams from pokepast.es URLs."""

import re
from typing import Optional

import httpx

from .cache import APICache
from ..config import settings, logger


class PokePasteError(Exception):
    """Error fetching from PokePaste."""
    pass


class PokePasteClient:
    """Client for fetching teams from pokepast.es."""

    # Pattern to extract paste ID from various URL formats
    URL_PATTERNS = [
        r"pokepast\.es/([a-zA-Z0-9]+)",  # pokepast.es/abc123
        r"pokepast\.es/([a-zA-Z0-9]+)/raw",  # pokepast.es/abc123/raw
    ]

    def __init__(self, cache: Optional[APICache] = None):
        """Initialize client with optional cache."""
        self.cache = cache or APICache()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with connection pooling."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.API_TIMEOUT_SECONDS),
                headers={"User-Agent": "VGC-MCP-Server/0.1.0"},
                follow_redirects=True,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        return self._client

    def extract_paste_id(self, url_or_id: str) -> Optional[str]:
        """Extract paste ID from a URL or return the ID if already bare.

        Args:
            url_or_id: Either a full URL like "https://pokepast.es/abc123"
                       or just the paste ID "abc123"

        Returns:
            The paste ID, or None if not found
        """
        # If it looks like just an ID (alphanumeric, no slashes/dots)
        if re.match(r'^[a-zA-Z0-9]+$', url_or_id):
            return url_or_id

        # Try to extract from URL patterns
        for pattern in self.URL_PATTERNS:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)

        return None

    async def get_paste_raw(self, paste_id: str) -> str:
        """Fetch the raw paste content.

        Args:
            paste_id: The paste ID (e.g., "abc123")

        Returns:
            Raw paste text in Showdown format

        Raises:
            PokePasteError: If fetch fails
        """
        # Check cache first
        cache_key = f"paste/{paste_id}"
        cached = self.cache.get("pokepaste", cache_key)
        if cached is not None:
            return cached

        client = await self._get_client()
        url = f"{settings.POKEPASTE_BASE_URL}/{paste_id}/raw"

        try:
            response = await client.get(url)

            if response.status_code == 404:
                raise PokePasteError(f"Paste not found: {paste_id}")

            response.raise_for_status()
            content = response.text

            # Cache the result
            self.cache.set("pokepaste", cache_key, content)
            logger.debug(f"Fetched PokePaste: {paste_id}")

            return content

        except httpx.HTTPStatusError as e:
            logger.warning(f"PokePaste HTTP error for {paste_id}: {e}")
            raise PokePasteError(f"HTTP error fetching paste: {e}")
        except httpx.RequestError as e:
            logger.warning(f"PokePaste network error for {paste_id}: {e}")
            raise PokePasteError(f"Network error fetching paste: {e}")

    async def get_paste(self, url_or_id: str) -> str:
        """Fetch paste content from a URL or paste ID.

        This is the main entry point - accepts either:
        - Full URL: "https://pokepast.es/abc123"
        - Partial URL: "pokepast.es/abc123"
        - Just ID: "abc123"

        Args:
            url_or_id: URL or paste ID

        Returns:
            Raw paste text in Showdown format

        Raises:
            PokePasteError: If URL is invalid or fetch fails
        """
        paste_id = self.extract_paste_id(url_or_id)
        if not paste_id:
            raise PokePasteError(
                f"Could not extract paste ID from: {url_or_id}. "
                "Expected format: pokepast.es/PASTE_ID or just PASTE_ID"
            )

        return await self.get_paste_raw(paste_id)

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "PokePasteClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
