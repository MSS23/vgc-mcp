"""Regression tests for session-aware Smogon chaos dataset routing."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.rules.regulation_loader import (
    RegulationConfig,
    get_regulation_config,
    reset_regulation_config,
)


class _Session:
    pass


class _RequestContext:
    def __init__(self, session):
        self.session = session


def _patch_session(session):
    class _RequestContextVar:
        def get(self):
            return _RequestContext(session)

    return patch("mcp.server.lowlevel.server.request_ctx", _RequestContextVar())


def _client(config=None):
    cache = MagicMock()
    cache.get.return_value = None
    return SmogonStatsClient(cache=cache, regulation_config=config)


def test_default_rating_policy_and_explicit_unweighted():
    config = RegulationConfig()
    config.set_session_regulation("reg_mb_champs")
    client = _client(config)
    formats = ["gen9championsvgc2026regmb"]

    assert client._ratings_to_try(None, formats) == [1630, 1500, 0]
    assert client._ratings_to_try(0, formats) == [0]
    assert client._ratings_to_try(1760, formats) == [1760]


@pytest.mark.asyncio
async def test_active_regulation_month_and_source_are_explicit():
    config = RegulationConfig()
    config.set_session_regulation("reg_mb_champs")
    client = _client(config)
    client._try_fetch_stats = AsyncMock(return_value={"data": {}})

    stats = await client.get_usage_stats(month="2026-06")

    client._try_fetch_stats.assert_awaited_once_with(
        "2026-06",
        "gen9championsvgc2026regmb",
        1630,
    )
    assert stats["_meta"] == {
        "format": "gen9championsvgc2026regmb",
        "month": "2026-06",
        "month_display": "June 2026 Usage Stats",
        "rating": 1630,
        "requested_rating": None,
        "source_url": (
            "https://www.smogon.com/stats/2026-06/chaos/gen9championsvgc2026regmb-1630.json"
        ),
    }


@pytest.mark.asyncio
async def test_default_cutoff_fallback_reports_the_resolved_rating():
    config = RegulationConfig()
    config.set_session_regulation("reg_mb_champs")
    client = _client(config)
    client._try_fetch_stats = AsyncMock(side_effect=[None, {"data": {}}])

    stats = await client.get_usage_stats(month="2026-06")

    assert client._try_fetch_stats.await_args_list[0].args[-1] == 1630
    assert client._try_fetch_stats.await_args_list[1].args[-1] == 1500
    assert stats["_meta"]["rating"] == 1500
    assert stats["_meta"]["requested_rating"] is None
    assert stats["_meta"]["source_url"].endswith("regmb-1500.json")


@pytest.mark.asyncio
async def test_request_metadata_does_not_mutate_a_shared_cached_payload():
    config = RegulationConfig()
    config.set_session_regulation("reg_mb_champs")
    client = _client(config)
    shared_payload = {"data": {}}
    client._try_fetch_stats = AsyncMock(return_value=shared_payload)

    automatic = await client.get_usage_stats(month="2026-06")
    explicit = await client.get_usage_stats(rating=1630, month="2026-06")

    assert automatic is not explicit
    assert automatic["_meta"]["requested_rating"] is None
    assert explicit["_meta"]["requested_rating"] == 1630
    assert "_meta" not in shared_payload


def test_shared_client_resolves_config_and_metadata_per_mcp_session():
    client = _client()
    first_session, second_session = _Session(), _Session()
    try:
        with _patch_session(first_session):
            first = get_regulation_config()
            first.set_session_regulation("reg_mb_champs")
            assert client.ACTIVE_VGC_FORMATS == ["gen9championsvgc2026regmb"]
            client._session_state().current_format = "gen9championsvgc2026regmb"

        with _patch_session(second_session):
            second = get_regulation_config()
            second.set_session_regulation("reg_i")
            assert client.ACTIVE_VGC_FORMATS == [
                "gen9vgc2026regibo3",
                "gen9vgc2026regi",
            ]
            assert client.current_format is None

        with _patch_session(first_session):
            assert client.current_format == "gen9championsvgc2026regmb"
    finally:
        reset_regulation_config()


def test_champions_regulation_letter_includes_full_suffix():
    config = RegulationConfig()
    client = _client(config)
    client._session_state().current_format = "gen9championsvgc2026regmb"
    assert client.current_regulation_from_data == "MB"
