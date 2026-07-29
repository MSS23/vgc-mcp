"""Tests for PokeAPI negative caching and in-flight request coalescing (2.2)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from vgc_mcp_core.api.pokeapi import PokeAPIClient, PokeAPIError


def _client_with_counter(status_ok: bool):
    """Return (client, counter) where counter['n'] tracks network calls."""
    cache = MagicMock()
    cache.get = MagicMock(return_value=None)
    cache.set = MagicMock()
    client = PokeAPIClient(cache)
    counter = {"n": 0}

    async def fake_get(url):
        counter["n"] += 1
        await asyncio.sleep(0.01)
        req = httpx.Request("GET", url)
        resp = MagicMock()
        if status_ok:
            resp.raise_for_status = MagicMock()
            resp.json = MagicMock(return_value={"url": url})
        else:
            resp.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError(
                    "404", request=req, response=httpx.Response(404, request=req)
                )
            )
        return resp

    http = AsyncMock()
    http.get = fake_get
    client._get_client = AsyncMock(return_value=http)
    return client, counter


async def test_404_is_negatively_cached():
    client, counter = _client_with_counter(status_ok=False)
    for _ in range(2):
        with pytest.raises(PokeAPIError):
            await client._fetch("pokemon/notreal")
    assert counter["n"] == 1  # second lookup short-circuits on the negative cache


async def test_concurrent_identical_fetches_coalesce():
    client, counter = _client_with_counter(status_ok=True)
    results = await asyncio.gather(
        *[client._fetch("pokemon/pikachu") for _ in range(5)]
    )
    assert counter["n"] == 1  # five concurrent callers, one network request
    assert all(r["url"].endswith("/pokemon/pikachu") for r in results)


async def test_negative_cache_expires():
    client, counter = _client_with_counter(status_ok=False)
    client.NEGATIVE_CACHE_TTL = 0.0  # immediately expired
    for _ in range(2):
        with pytest.raises(PokeAPIError):
            await client._fetch("pokemon/notreal")
    # With a 0s TTL each call re-checks the network.
    assert counter["n"] == 2
