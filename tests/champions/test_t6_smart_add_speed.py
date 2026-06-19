"""T6 regression tests: add_pokemon_smart + find_speed_evs_to_outspeed in a
Champions (Reg MA) session.

These call the ACTUAL registered @mcp.tool handlers (not the pure helpers) and
assert SP-scale output (cap 32/stat, 66 total, 'SPs:' paste line) for champions
while leaving the mainline path byte-for-byte unchanged.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.workflow_tools import register_workflow_tools
from vgc_mcp.tools.speed_analysis_tools import register_speed_analysis_tools
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.team.manager import TeamManager
from vgc_mcp_core.rules.regulation_loader import get_regulation_config


# Flutter Mane base stats (a Champions-legal Pokemon).
FLUTTER_MANE = BaseStats(
    hp=55, attack=55, defense=55,
    special_attack=135, special_defense=135, speed=135,
)


@pytest.fixture
def champions_session():
    """Force a Champions session for the duration of the test, then reset."""
    cfg = get_regulation_config()
    cfg.clear_session_override()
    cfg.set_session_regulation("reg_ma_champs")
    yield cfg
    cfg.clear_session_override()


@pytest.fixture
def mainline_session():
    cfg = get_regulation_config()
    cfg.clear_session_override()
    yield cfg
    cfg.clear_session_override()


def _mock_pokeapi():
    api = AsyncMock()
    api.get_base_stats = AsyncMock(return_value=FLUTTER_MANE)
    api.get_pokemon_types = AsyncMock(return_value=["ghost", "fairy"])
    api.get_pokemon_abilities = AsyncMock(return_value=["Protosynthesis"])
    return api


def _workflow_tools(api, team_manager):
    mcp = FastMCP("test")
    register_workflow_tools(mcp, api, AsyncMock(), team_manager, AsyncMock())
    return {t.name: t.fn for t in mcp._tool_manager._tools.values()}


def _speed_tools(api):
    mcp = FastMCP("test")
    register_speed_analysis_tools(mcp, api, MagicMock(), AsyncMock())
    return {t.name: t.fn for t in mcp._tool_manager._tools.values()}


# --------------------------------------------------------------------------
# T6-a: add_pokemon_smart
# --------------------------------------------------------------------------

class TestAddPokemonSmartChampions:
    async def test_emits_sp_scale_build(self, champions_session):
        fn = _workflow_tools(_mock_pokeapi(), TeamManager())["add_pokemon_smart"]
        r = await fn(pokemon_name="flutter-mane", role="sweeper")

        assert r.get("success") is True, r
        assert r["format_system"] == "champions"

        build = r["build"]
        assert "sps" in build
        assert "evs" not in build, "champions build must not surface an EV map"
        sps = build["sps"]
        # SP grain: cap 32 per stat, <=66 total.
        assert all(0 <= v <= 32 for v in sps.values()), sps
        assert sum(sps.values()) <= 66, sps
        # Sweeper -> max offense (SpA for Flutter Mane) + max Speed.
        assert sps["spa"] == 32
        assert sps["spe"] == 32

    async def test_paste_uses_sps_line(self, champions_session):
        fn = _workflow_tools(_mock_pokeapi(), TeamManager())["add_pokemon_smart"]
        r = await fn(pokemon_name="flutter-mane", role="sweeper")

        paste = r["showdown_paste"]
        assert "SPs:" in paste
        assert "EVs:" not in paste
        # Never emit mainline 252/508 numbers for a champions build.
        assert "252" not in paste and "508" not in paste

    async def test_surfaces_regulation_auto_detected_from_mega(self, mainline_session):
        # Clean session + a Mega name should auto-detect Champions and surface it.
        api = _mock_pokeapi()
        api.get_pokemon_types = AsyncMock(return_value=["electric"])
        api.get_pokemon_abilities = AsyncMock(return_value=["Intimidate"])
        fn = _workflow_tools(api, TeamManager())["add_pokemon_smart"]
        r = await fn(pokemon_name="manectric-mega")

        assert r["format_system"] == "champions"
        detected = r.get("regulation_auto_detected")
        assert detected is not None
        assert detected.get("regulation") == "reg_ma_champs"
        assert detected.get("action") == "set"
        assert "SPs:" in r["showdown_paste"]
        # Species line normalized to a valid Showdown name.
        assert r["showdown_paste"].splitlines()[0] == "Manectric-Mega"


class TestAddPokemonSmartMainline:
    async def test_mainline_unchanged(self, mainline_session):
        fn = _workflow_tools(_mock_pokeapi(), TeamManager())["add_pokemon_smart"]
        r = await fn(pokemon_name="flutter-mane", role="sweeper")

        assert r.get("success") is True, r
        assert r["format_system"] == "mainline"
        build = r["build"]
        assert "evs" in build
        assert "sps" not in build
        assert build["evs"] == {"spa": 252, "spe": 252, "hp": 4}
        paste = r["showdown_paste"]
        assert "EVs:" in paste
        assert "SPs:" not in paste


# --------------------------------------------------------------------------
# T6-b: find_speed_evs_to_outspeed
# --------------------------------------------------------------------------

class TestSpeedOutspeedChampions:
    async def test_reports_sp_budget(self, champions_session):
        fn = _speed_tools(_mock_pokeapi())["find_speed_evs_to_outspeed"]
        r = await fn(pokemon_name="flutter-mane", target_speed=180, nature="timid")

        assert r["achievable"] is True
        assert r["format_system"] == "champions"
        assert r["stat_units"] == "Stat Points (SPs)"
        # SP-scale, not EV-scale.
        assert "sps_needed" in r and "evs_needed" not in r
        assert "sps_remaining" in r and "evs_remaining" not in r
        assert 0 <= r["sps_needed"] <= 32
        assert r["sps_needed"] + r["sps_remaining"] == 66
        # Reaches/exceeds the requested stat.
        assert r["actual_speed"] >= 180
        # No EV-budget nonsense (68 EV / 440 remaining) leaks through.
        assert r["sps_needed"] < 32
        assert r["sps_remaining"] <= 66

    async def test_unreachable_reports_sp_max(self, champions_session):
        fn = _speed_tools(_mock_pokeapi())["find_speed_evs_to_outspeed"]
        r = await fn(pokemon_name="flutter-mane", target_speed=999, nature="timid")

        assert r["achievable"] is False
        assert r["format_system"] == "champions"
        assert "max_speed_with_32_sps" in r
        assert "max_speed_with_252_evs" not in r


class TestSpeedOutspeedMainline:
    async def test_mainline_unchanged(self, mainline_session):
        fn = _speed_tools(_mock_pokeapi())["find_speed_evs_to_outspeed"]
        r = await fn(pokemon_name="flutter-mane", target_speed=180, nature="timid")

        assert r["achievable"] is True
        assert "evs_needed" in r and "sps_needed" not in r
        assert "evs_remaining" in r and "sps_remaining" not in r
        assert r["evs_remaining"] == 508 - r["evs_needed"]
