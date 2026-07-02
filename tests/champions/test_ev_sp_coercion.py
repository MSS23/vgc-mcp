"""Regression tests: EV-scale input auto-converts to Stat Points in Champions.

Users porting mainline sets routinely pass EV numbers (252 SpA, 196 HP, ...)
to tools with EV-named parameters while a Champions regulation is active.
Before the coercion layer these calls failed the 32/stat SP cap with
"252 SP exceeds per-stat max (32)". Now any allocation with a stat > 32 is
unambiguously EV-scale and converts via 1 SP = 8 EVs (rounded up, trimmed to
the 66 budget), with an `sp_conversion` note in the response.

Native SP input (all stats 0-32) must pass through untouched, and mainline
sessions must never convert.
"""

from unittest.mock import AsyncMock

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.build_tools import register_build_tools
from vgc_mcp.tools.team_tools import register_team_tools
from vgc_mcp_core.calc.conversion import coerce_champions_allocation
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.rules.regulation_loader import (
    get_regulation_config,
    reset_regulation_config,
)
from vgc_mcp_core.state.build_manager import BuildStateManager
from vgc_mcp_core.team.analysis import TeamAnalyzer
from vgc_mcp_core.team.manager import TeamManager

RAGING_BOLT_BASE = BaseStats(
    hp=125, attack=73, defense=91,
    special_attack=137, special_defense=89, speed=75,
)


@pytest.fixture
def champions_session():
    reset_regulation_config()
    cfg = get_regulation_config()
    cfg.set_session_regulation("reg_ma_champs", by_user=True)
    assert cfg.get_format_system() == "champions"
    yield cfg
    reset_regulation_config()


@pytest.fixture
def mainline_session():
    reset_regulation_config()
    cfg = get_regulation_config()
    cfg.set_session_regulation("reg_g", by_user=True)
    assert cfg.get_format_system() == "mainline"
    yield cfg
    reset_regulation_config()


@pytest.fixture
def mock_pokeapi():
    client = AsyncMock()
    client.get_base_stats = AsyncMock(return_value=RAGING_BOLT_BASE)
    client.get_pokemon_types = AsyncMock(return_value=["Electric", "Dragon"])
    client.get_pokemon_abilities = AsyncMock(return_value=["Protosynthesis"])
    return client


@pytest.fixture
def team_tools(mock_pokeapi):
    mcp = FastMCP("test")
    team_manager = TeamManager()
    analyzer = TeamAnalyzer()
    register_team_tools(mcp, mock_pokeapi, team_manager, analyzer)
    return {t.name: t for t in mcp._tool_manager._tools.values()}, team_manager


@pytest.fixture
def build_tools(mock_pokeapi):
    mcp = FastMCP("test")
    build_manager = BuildStateManager()
    register_build_tools(mcp, build_manager, mock_pokeapi)
    return {t.name: t for t in mcp._tool_manager._tools.values()}, build_manager


# ------------------------- unit: the coercion rule -------------------------

class TestCoerceChampionsAllocation:
    def test_ev_scale_converts(self):
        alloc, note = coerce_champions_allocation({
            "hp": 196, "attack": 0, "defense": 36,
            "special_attack": 252, "special_defense": 0, "speed": 0,
        })
        assert alloc == {
            "hp": 25, "attack": 0, "defense": 5,
            "special_attack": 32, "special_defense": 0, "speed": 0,
        }
        assert note is not None
        assert note["original_evs"] == {"hp": 196, "defense": 36, "special_attack": 252}

    def test_native_sp_untouched(self):
        original = {
            "hp": 24, "attack": 0, "defense": 5,
            "special_attack": 32, "special_defense": 0, "speed": 0,
        }
        alloc, note = coerce_champions_allocation(original)
        assert alloc == original
        assert note is None

    def test_over_budget_sp_not_converted(self):
        # All stats fit 0-32 but total > 66: plausibly an over-budget SP
        # attempt, NOT a tiny EV spread. Must stay unconverted so the
        # validator reports "total exceeds 66".
        original = {
            "hp": 30, "attack": 30, "defense": 30,
            "special_attack": 0, "special_defense": 0, "speed": 0,
        }
        alloc, note = coerce_champions_allocation(original)
        assert alloc == original
        assert note is None

    def test_max_ev_spread_trims_to_budget(self):
        # 252/252/252 EV -> 32/32/32 SP = 96 raw, must trim to <= 66.
        alloc, note = coerce_champions_allocation({
            "hp": 252, "attack": 252, "defense": 0,
            "special_attack": 0, "special_defense": 0, "speed": 252,
        })
        assert note is not None
        assert sum(alloc.values()) <= 66
        assert all(0 <= v <= 32 for v in alloc.values())


# ------------------------- tool: add_to_team -------------------------------

class TestAddToTeamCoercion:
    async def test_ev_input_converts_and_succeeds(self, champions_session, team_tools):
        tools, team_manager = team_tools
        result = await tools["add_to_team"].fn(
            pokemon_name="raging-bolt", nature="modest",
            hp_evs=196, def_evs=36, spa_evs=252,
        )
        assert result["success"] is True, result.get("message")
        assert result["sp_conversion"]["converted_sps"] == {
            "hp": 25, "defense": 5, "special_attack": 32,
        }
        stored = team_manager.team.slots[0].pokemon
        assert stored.format_system == "champions"
        assert stored.sps.hp == 25
        assert stored.sps.defense == 5
        assert stored.sps.special_attack == 32

    async def test_native_sp_input_no_conversion(self, champions_session, team_tools):
        tools, team_manager = team_tools
        result = await tools["add_to_team"].fn(
            pokemon_name="raging-bolt", nature="modest",
            hp_evs=24, def_evs=5, spa_evs=32,
        )
        assert result["success"] is True, result.get("message")
        assert "sp_conversion" not in result
        stored = team_manager.team.slots[0].pokemon
        assert stored.sps.hp == 24

    async def test_mainline_evs_never_converted(self, mainline_session, team_tools):
        tools, team_manager = team_tools
        result = await tools["add_to_team"].fn(
            pokemon_name="raging-bolt", nature="modest",
            hp_evs=196, def_evs=36, spa_evs=252,
        )
        assert result["success"] is True, result.get("message")
        assert "sp_conversion" not in result
        stored = team_manager.team.slots[0].pokemon
        assert stored.format_system != "champions"
        assert stored.evs.hp == 196
        assert stored.evs.special_attack == 252


class TestSwapTeamPokemonCoercion:
    async def test_ev_input_converts(self, champions_session, team_tools):
        tools, team_manager = team_tools
        r = await tools["add_to_team"].fn(pokemon_name="raging-bolt", nature="modest", spa_evs=32)
        assert r["success"] is True
        result = await tools["swap_team_pokemon"].fn(
            slot=1, pokemon_name="raging-bolt", nature="timid",
            spa_evs=252, spe_evs=196,
        )
        assert result["success"] is True, result.get("message")
        assert result["sp_conversion"]["converted_sps"] == {
            "special_attack": 32, "speed": 25,
        }


# ------------------------- tool: build state -------------------------------

class TestBuildToolsCoercion:
    async def test_create_build_ev_input_converts(self, champions_session, build_tools):
        tools, _ = build_tools
        result = await tools["create_build"].fn(
            pokemon_name="raging-bolt", nature="modest",
            hp_evs=4, spa_evs=252, spe_evs=252,
        )
        assert result["success"] is True, result.get("message")
        assert result["build"]["sps"] == {
            "hp": 1, "attack": 0, "defense": 0,
            "special_attack": 32, "special_defense": 0, "speed": 32,
        }
        assert "sp_conversion" in result

    async def test_modify_build_ev_edit_converts(self, champions_session, build_tools):
        tools, _ = build_tools
        r = await tools["create_build"].fn(
            pokemon_name="raging-bolt", nature="modest", spa_evs=32, spe_evs=20,
        )
        assert r["success"] is True
        result = await tools["modify_build"].fn(
            pokemon_name="raging-bolt", spa_evs=180,  # EV-scale -> 23 SP
        )
        assert result["success"] is True, result.get("message")
        assert result["build"]["sps"]["special_attack"] == 23
        assert "sp_conversion" in result

    async def test_modify_build_over_budget_rejected(self, champions_session, build_tools):
        tools, _ = build_tools
        r = await tools["create_build"].fn(
            pokemon_name="raging-bolt", nature="modest", spa_evs=32, spe_evs=32, hp_evs=1,
        )
        assert r["success"] is True
        # 116 EVs -> 15 SP; 15 + 32 + 32 = 79 > 66 must be rejected clearly.
        result = await tools["modify_build"].fn(pokemon_name="raging-bolt", hp_evs=116)
        assert "error" in result
        assert "66" in result.get("message", "")
