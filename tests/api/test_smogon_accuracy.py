"""Chaos inclusion rates, data failures, and like-for-like trend regressions."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from vgc_mcp_core.api.smogon import SmogonStatsClient, SmogonStatsError
from vgc_mcp_core.rules.regulation_loader import RegulationConfig


def client():
    cache = MagicMock()
    cache.get.return_value = None
    return SmogonStatsClient(cache, RegulationConfig())


def payload(usage=0.3):
    # Ten weighted occurrences, four moves each, five teammates each.
    return {"data": {"Landorus": {
        "usage": usage,
        "Raw count": 1000,  # Unweighted count must NOT be the denominator.
        "Abilities": {"sheerforce": 10},
        "Items": {"lifeorb": 10},
        "Spreads": {"Modest:4/0/0/252/0/252": 10},
        "Moves": {"earthpower": 10, "protect": 10, "sludgebomb": 10, "psychic": 10},
        "Teammates": {name: 10 for name in ("A", "B", "C", "D", "E")},
    }}}


async def test_move_and_teammate_usage_is_percent_of_pokemon():
    smogon = client()
    smogon._try_fetch_stats = AsyncMock(return_value=payload())
    sets = await smogon.get_common_sets("landorus-incarnate", "gen9vgc2026regi", month="2026-07")
    assert all(move["usage"] == 100 for move in sets["top_moves"])
    assert sets["top_spreads"][0]["usage"] == 100
    assert "not observed complete sets" in sets["set_methodology"]
    teammates = await smogon.suggest_teammates("landorus-incarnate")
    assert all(mon["usage_with"] == 100 for mon in teammates["suggested_teammates"])


async def test_missing_move_slots_are_not_recommended():
    smogon = client()
    data = payload()
    data["data"]["Landorus"]["Moves"] = {"earthpower": 10, "": 20, "Nothing": 10}
    smogon._try_fetch_stats = AsyncMock(return_value=data)
    sets = await smogon.get_common_sets("landorus")
    assert sets["top_moves"] == [{"name": "earthpower", "usage": 100}]


async def test_trends_use_resolved_month_rating_format_and_form_alias():
    smogon = client()
    smogon._get_recent_months = MagicMock(return_value=["2026-02", "2026-01"])

    async def fetch(month, fmt, rating):
        if month == "2026-02" or rating != 1500:
            return None
        return payload(0.3 if month == "2026-01" else 0.2)

    smogon._try_fetch_stats = AsyncMock(side_effect=fetch)
    result = await smogon.compare_pokemon_usage("landorus-incarnate", "gen9vgc2026regi")
    assert result["current_month"] == "2026-01"
    assert result["previous_month"] == "2025-12"
    assert result["current"]["usage_percent"] == 30
    assert result["previous"]["usage_percent"] == 20
    assert smogon._try_fetch_stats.await_args_list[-1].args == (
        "2025-12", "gen9vgc2026regi", 1500
    )
    assert smogon.current_month == "2026-01"


async def test_missing_history_is_not_replaced_with_another_cutoff():
    smogon = client()
    smogon._get_recent_months = MagicMock(return_value=["2026-08"])
    smogon._try_fetch_stats = AsyncMock(side_effect=[payload(), None])
    result = await smogon.compare_pokemon_usage("landorus", "gen9vgc2026regi", 1630)
    assert result["previous"] is None
    assert result["changes"] == []


@pytest.mark.parametrize("body", ["not json", "[]", '{"error": "unavailable"}'])
async def test_invalid_responses_are_not_cached(body):
    smogon = client()
    smogon._client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, text=body)
    ))
    try:
        with pytest.raises(SmogonStatsError):
            await smogon.get_usage_stats("gen9vgc2026regi", 1630, "2026-08")
        smogon.cache.set.assert_not_called()
    finally:
        await smogon.close()
